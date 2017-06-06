import sys
import os

if __name__ == '__main__':
    try:
        os.system("xvfb-run -a --server-args='-screen 0 1360x768x24' /home/dmcAdmin/anaconda2/bin/python generateTDP.py")
    except:
        sys.exit(0)
