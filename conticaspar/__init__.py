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
        self.playlist = []
        self.cued_item = None
        self.current_item = None
        self.current_duration = 0
        self.current_position = 0

        self.feed_key = "{}-{}".format(self.settings["feed_channel"], self.settings["feed_layer"])
        self.num_fails = 0
        self.cueing = False

        if not self.connect():
            raise Exception, "Unable to connect CasparCG server"


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
        return True

    def playlist_thread(self):
        self.running_threads += 1
        while self.should_run:
            try:
                self.playlist_main()
            except Exception:
                log_traceback()
            time.sleep(1)
        logging.debug("Stopping playlist thread")
        self.running_threads -= 1

    def progress_thread(self):
        self.running_threads += 1
        while self.should_run:
            try:
                self.progress_main()
            except Exception:
                log_traceback()
            time.sleep(.2)
        logging.debug("Stopping progress thread")
        self.running_threads -= 1

    def caspar_thread(self):
        if not self.settings["blocking"]:
            self.running_threads += 1
        while self.should_run:
            try:
                self.caspar_main()
            except Exception:
                log_traceback()
            time.sleep(.2)
        logging.debug("Stopping caspar thread")
        self.running_threads -= 1



    def playlist_main(self):
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


    def progress_main(self):
        pass


    def caspar_main(self):
        response = self.caspar.query("INFO {}".format(self.feed_key))
        if response.is_error:
            time.sleep(.1)
            if self.num_fails > 3:
                self.connect()
                self.num_fails = 0
            self.num_fails += 1
            return
        self.num_fails = 0
        info = xml(response.data)

        try:
            cued_file = info.find("background").find("producer").find("destination").find("producer").find("filename").text
        except Exception:
            cued_file = False

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

