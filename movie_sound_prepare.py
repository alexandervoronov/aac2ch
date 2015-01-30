#!python3

import argparse
import re
import subprocess
import os

def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument('-i', '--input', dest='input', type=str,
                        required=True, help='Input movie file.')
    
    return parser.parse_args()

def extract_audio_streams(input_file):
    if input_file.find(' ') != -1:
        input_file = '"{}"'.format(input_file)
    exec_line = 'ffmpeg.exe -i {}'.format(input_file)
    out = ''
    err = ''
    try:
        # out = subprocess.check_output(exec_line, stderr=os.devnull)
        p = subprocess.Popen(exec_line, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        out, err = p.communicate()
        out = str(out, encoding='utf8')
        err = str(err, encoding='utf8')
    except:
        pass
    # print(err.replace('Stream', 'Tratata'))

    re_pattern = 'Stream #.*?Audio.*?$'
    streams = re.findall(re_pattern, err, re.M)
    print('\n'.join(streams))
    print('ok')

if __name__ == '__main__':
    args = parse_args()
    extract_audio_streams(args.input)
