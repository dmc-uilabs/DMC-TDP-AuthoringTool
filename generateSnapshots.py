import sys
from PyQt5 import QtWidgets
from OCC.Display.OCCViewer import Viewer3d
from PIL import Image
from tdpUtility import import_step, FILENAME, SNAPSHOTS_FILE

VIEWS = ["front", "rear", "top", "bottom", "left", "right", "iso"]

def generate_snapshots(shape):
    print "Generating snapshots..."

    try:
        app = QtWidgets.QApplication(sys.argv)
        widget = QtWidgets.QWidget()
        widget.resize(1000,1000)
        view = Viewer3d(int(widget.winId()))
        view.Create()
        view.SetModeShaded()
        view.DisplayShape(shape, update=True)

        VIEW_FUNC = {
            "front": view.View_Front,
            "rear": view.View_Rear,
            "top": view.View_Top,
            "bottom": view.View_Bottom,
            "left": view.View_Left,
            "right": view.View_Right,
            "iso": view.View_Iso
        }

        snapshots = []

        for view_type in VIEWS:
            VIEW_FUNC[view_type]()
            view.ExportToImage('capture.ppm')
            im = Image.open('capture.ppm')
            snapshot = view_type + '_capture.png'
            im.save(snapshot)
            snapshots.append(snapshot)
    except:
        sys.exit(1)

    return snapshots

def write_to_file(snapshots):
    outfile = open(SNAPSHOTS_FILE, 'w')

    for snapshot in snapshots:
        outfile.write(snapshot + '\n')

    outfile.close()

if __name__ == '__main__':
    try:
        shape = import_step(FILENAME)
        snapshots = generate_snapshots(shape)
        write_to_file(snapshots)
    except:
        sys.exit(1)
    sys.exit(0)
