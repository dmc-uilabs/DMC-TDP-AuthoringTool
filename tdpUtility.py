import aocxchange.step

FILENAME = "inputFile.stp"
SNAPSHOTS_FILE = "snapshots.txt"

def import_step(filename):
    print "Importing shapes from STP file..."
    
    try:
        my_importer = aocxchange.step.StepImporter(filename)
        assert(len(my_importer.shapes))
        print str(len(my_importer.shapes)) + " shapes loaded..."
    except:
        raise Exception("Error importing shapes from STP file.")
        
    return my_importer.shapes[0]
