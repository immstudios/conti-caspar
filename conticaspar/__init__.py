import time

from nxtools import *
from nxtools.caspar import *
from nxtools.media import *

from .item import ContiCasparItem


__all__ = ["ContiCaspar", "ContiCasparItem"]


if PYTHON_VERSION < 3:
    import thread
else:
    import _thread as thread


class ContiCaspar(object):
    def __init__(self, get_next_item, **kwargs):
        self.get_next_item = get_next_item
        self.settings = {
                "blocking" : True,
                "feed_channel" : 1,
                "feed_layer" : 10,
                "caspar_host" : "localhost",
                "caspar_port" : 5250,
                "playlist_length" : 5,
            }
        for key in kwargs:
            if key in self.settings:
               self.settings[key] = kwargs[key]

        self.should_run = True
        self.running_threads = 0

        self.caspar = None
        self.caspar_info = None
        self.playlist = []
        self.cued_item = None
        self.current_item = None
        self.current_duration = 0
        self.current_position = 0
        self.stopped = False
        self.paused = False

        self.feed_key = "{}-{}".format(self.settings["feed_channel"], self.settings["feed_layer"])
        self.num_fails = 0
        self.cueing = False

        self.need_progress_update = False
        self.progress_thread_running = False
        self.need_change_update = False
        self.change_thread_running = False

        if not self.connect():
            raise Exception("Unable to connect CasparCG server")


    def start(self):
        thread.start_new_thread(self.playlist_thread, ())
        thread.start_new_thread(self.progress_thread, ())
        if self.settings["blocking"]:
            self.caspar_thread()
        else:
            thread.start_new_thread(self.caspar_thread, ())

    def stop(self):
        self.should_run = False
        while self.running_threads > 0:
            logging.debug("Waiting for {} threads to terminate".format(self.running_threads))
            time.sleep(.2)

    def connect(self):
        self.caspar = CasparCG(
                self.settings["caspar_host"],
                self.settings["caspar_port"],
            )
        self.caspar_info = CasparCG(
                self.settings["caspar_host"],
                self.settings["caspar_port"],
            )
        return True

    def playlist_thread(self):
        self.running_threads += 1
        while self.should_run:
            self.playlist_main()
            time.sleep(1)
        logging.debug("Stopping playlist thread")
        self.running_threads -= 1

    def progress_thread(self):
        self.running_threads += 1
        while self.should_run:
            self.progress_main()
            time.sleep(.2)
        logging.debug("Stopping progress thread")
        self.running_threads -= 1

    def caspar_thread(self):
        if not self.settings["blocking"]:
            self.running_threads += 1
        while self.should_run:
            self.caspar_main()
            time.sleep(.2)
        logging.debug("Stopping caspar thread")
        self.running_threads -= 1


    def playlist_main(self):
        try:
            while len(self.playlist) < self.settings["playlist_length"]:
                logging.debug("Fill playlist!")
                next_items = self.get_next_item(self)
                if type(next_items) != list:
                    next_items = [next_items]
                for next_item in next_items:
                    if not isinstance(next_item, ContiCasparItem):
                        logging.warning("Item must be of ContiCasparItem instance. Skipping. (is {})".format(type(next_item)))
                        continue
                    next_item.open(self)
                    if not next_item:
                        logging.error("Unable to open {}".format(next_item))
                        return
                    logging.info("Appending {} to playlist".format(next_item))
                    self.playlist.append(next_item)
        except Exception:
            log_traceback()


    def progress_main(self):
        try:
            if self.need_progress_update and not self.progress_thread_running:
                thread.start_new_thread(self.run_progress_thread, ())

            if self.need_change_update and not self.change_thread_running:
                thread.start_new_thread(self.run_change_thread, ())
        except Exception:
            log_traceback()

    def run_progress_thread(self):
        try:
            self.need_progress_update = False
            self.progress_thread_running = True
            self.on_progress(self)
            self.progress_thread_running = False
        except Exception:
            log_traceback()
            self.progress_thread_running = False

    def run_change_thread(self):
        try:
            self.need_change_update = False
            self.change_thread_running = True
            self.on_change(self)
            self.change_thread_running = False
        except Exception:
            log_traceback()
            self.change_thread_running = False

    def on_progress(self, parent):
        pass

    def on_change(self, parent):
        pass


    def caspar_main(self):
        try:
            response = self.caspar_info.query("INFO {}".format(self.feed_key))
            if response.is_error:
                time.sleep(.1)
                if self.num_fails > 3:
                    self.connect()
                    self.num_fails = 0
                self.num_fails += 1
                return
            self.num_fails = 0
            video_layer = xml(response.data)

            try:
                cued_file = video_layer.find("background").find("producer").find("destination").find("producer").find("filename").text
            except Exception:
                cued_file = False

            try:
                if video_layer.find("status").text == "paused":
                    self.paused = True
                    self.stopped = False
                elif video_layer.find("status").text == "stopped" or int(video_layer.find("frames-left").text) <= 0:
                    self.stopped = True
                    self.paused = False
                elif video_layer.find("status").text == "playing":
                    self.paused = False
                    self.stopped = False

                fg_prod = video_layer.find("foreground").find("producer")
                if fg_prod.find("type").text == "image-producer":
                    self.current_position = 0
                    self.current_duration = 0
                    self.current_file_position = 0
                    self.current_file_duration = 0
#                current_fname = get_base_name(fg_prod.find("location").text)
                elif fg_prod.find("type").text == "empty-producer":
                    current_fname = False # No video is playing right now
                else:
                    self.current_file_postion = int(fg_prod.find("file-frame-number").text)
                    self.current_file_duration = int(fg_prod.find("file-nb-frames").text)
                    self.current_position  = int(fg_prod.find("frame-number").text)
                    self.current_duration  = int(fg_prod.find("nb-frames").text)
#                current_fname = get_base_name(fg_prod.find("filename").text)
            except Exception:
                log_traceback()
                pass


            if cued_file:
                self.cueing = False

            if not cued_file and not self.cueing and self.playlist:
                self.current_item = self.cued_item

                self.cued_item = self.playlist.pop(0)
                logging.info("Cueing {}".format(self.cued_item))
                next_file = self.cued_item.base_name
                mark_in = self.cued_item.settings.get("mark_in", 0)
                mark_out = self.cued_item.settings.get("mark_out", 0)
                opts = ""
                #TODO: if mark_in: opts += ....
                self.caspar.query("LOADBG {} {} AUTO{}".format(self.feed_key, next_file, opts))
                if self.current_item:
                    self.cueing = True
                self.need_change_update = True
            self.need_progress_update = True
        except Exception:
            log_traceback()

