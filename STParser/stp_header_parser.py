import re

class stp_header_parser():

    def stp_header_parser(self, stp_filename='', is_debug=False):

        def get_unit_abbr(units):
            prefix = {'MILLI': 'm'}
            unit = {'METRE': 'm'}
            return prefix[units[0]]+unit[units[1]]
            
        def remove_comments(line):
            comment_pattern = re.compile('/\*.*?\*/')
            return comment_pattern.sub('', line)
        
        def line_extract(filehandle=None, str_startswith='', str_endswith=''):

            while True:

                line = filehandle.readline().strip()
                #if line.startswith(str_startswith):
                if str_startswith in line:
                    line_extracted = ''
                    while True:
                        line_extracted += line
                        if line.endswith(str_endswith):
                            break
                        else:
                            line = filehandle.readline().strip()

                    return line_extracted

        infos_name = [
            'ISO Standard',
            'Description',
            'Implementation Level',
            'Name',
            'Time_Stamp',
            'Author',
            'Organization',
            'Preprocessor Version',
            'Originating System',
            'Authorization',
            'Schema',
            'Unit'
        ]

        infos_value = []

        len_infos_name = len(infos_name)

        with open(stp_filename, 'r') as f:
            
            line = line_extract(f, 'ISO-', ';')

            if line:
                ISO_Standard = line[:-1]
                infos_value.append(ISO_Standard)

            line = line_extract(f, 'HEADER', ';')

            if line:
                if is_debug:
                    print('>>> Header Start Mark Found <<<')

                line = line_extract(f, 'FILE_DESCRIPTION', ';')
                line = remove_comments(line)
                File_Description = eval(line[16:-1])
                infos_value += File_Description

                line = line_extract(f, 'FILE_NAME', ';')
                line = remove_comments(line)
                File_Name = eval(line[9:-1])
                infos_value += File_Name

                line = line_extract(f, 'FILE_SCHEMA', ';')
                line = remove_comments(line)
                File_Schema = eval(line[11:-1])
                infos_value.append(File_Schema)

                if line_extract(f, 'ENDSEC', ';'):
                    if is_debug:
                        print('>>> Header End Mark Found <<<')
            
            while True:
                line = line_extract(f, 'LENGTH_UNIT', ';')
                units = line.split('SI_UNIT')
                if(len(units) == 2):
                    units = units[1].split('.')[1:4:2]
                    units = get_unit_abbr(units)
                    infos_value.append(units)
                    break
                

        infos_dict = {
            index: list(parameter) for (
                index, parameter) in zip(
                range(len_infos_name), zip(
                    infos_name, infos_value))}

        if is_debug:
            for key in infos_dict:
                print('{:02}\t{}'.format(key, infos_dict[key]))

        return infos_dict