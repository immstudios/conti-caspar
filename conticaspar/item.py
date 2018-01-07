from nxtools import *
from nxtools.media import *

class ContiCasparItem(object):
    def __init__(self, path, **kwargs):
        self.path = path
        self.settings = kwargs
        self.meta = {
                "fps" : 25,
                "width" : 1920,
                "height" : 1080,
            }

    @property
    def base_name(self):
        return get_base_name(self.path)

    def open(self, parent):
        probe_result = ffprobe(self.path)
        if not probe_result:
            return False
        #TODO: Fill meta
        return True

    def __repr__(self):
        return "item:{}".format(self.base_name)

