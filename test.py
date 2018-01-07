#!/usr/bin/env python

import os
import sys

from conticaspar import *


class Items(object):
    def __init__(self):
        self.files = [f for f in os.listdir("/data/nxtv/playout.dir") if f.startswith("d")]
        self.i = 0

    def next(self, parent, **kwargs):
        self.i += 1
        index = self.i % len(self.files)
        return ContiCasparItem("/data/nxtv/playout.dir/" + self.files[index])



if __name__ == "__main__":
    itms = Items()
    c = ContiCaspar(
            itms.next,
            caspar_host="192.168.4.108"
        )
    try:
        c.start()
    except KeyboardInterrupt:
        print ()
        c.stop()





