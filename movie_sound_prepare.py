#!python3

import argparse
import re
import sarge
import subprocess
import os
import datetime
import hashlib

def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument('-i', '--input', dest='input', type=str,
                        required=True, help='Input movie file.')
    
    return parser.parse_args()

def generate_temp_name(prefix, extension):
    dt_string = str(datetime.datetime.now())
    md5_obj = hashlib.md5()
    md5_obj.update(bytearray(dt_string, encoding='utf8'))
    random_string = md5_obj.hexdigest()
    return prefix + '_' + random_string + '.' + extension

def parse_stream_info(stream_line):
    stream_info = {}
    pattern = '^Stream #\d:\d\((?P<lang>[a-z]{3})\): Audio: (?P<codec>[a-zA-Z0-9]{1,5}), .*?, (?P<channels>.*?),.*$'
    s_match = re.match(pattern, stream_line)
    keys = ['codec', 'lang', 'channels']
    if s_match:
        stream_info = { key : s_match.group(key) for key in keys}
    return stream_info

def extract_audio_streams(input_file, lang='eng'):
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

    stream_info = [parse_stream_info(single_line) for single_line in streams]
    for idx in range(len(stream_info)):
        stream_info[idx]['index'] = idx
    stream_info = [single_stream for single_stream in stream_info if single_stream['lang'] == lang]

    return stream_info

def encode_streams(input_file, stream_info):
    ffmpeg_2ch = ' -ac 2 '
    whole_pattern = 'ffmpeg -i {0} -vn -sn -map 0:a:{1} -af "aresample=async=1" {2} -f wav - | neroaacenc -q 0.xx -ignorelength -if - -of temp.m4a'
    ffmpeg_pattern = 'ffmpeg -i {0} -vn -sn -map 0:a:{1} -af "aresample=async=1" {2} -f wav -'
    aac_pattern = 'neroaacenc -q 0.42 -ignorelength -if - -of {}'
    if input_file.find(' ') != -1:
        input_file = '"{}"'.format(input_file)
    for stream in stream_info:
        tempname = generate_temp_name('stream{}'.format(stream['index']), 'm4a')
        stream['tempfile'] = tempname
        channel_setting = ffmpeg_2ch if stream['channels'].find('5.1') != -1 else ''
        ffmpeg_line = ffmpeg_pattern.format(input_file, stream['index'], channel_setting)
        aac_line = aac_pattern.format(tempname)
        print (ffmpeg_line)
        print (aac_line)
        sarge.run(ffmpeg_line + ' | ' + aac_line)


if __name__ == '__main__':
    args = parse_args()
    streams = extract_audio_streams(args.input)
    streams = encode_streams(args.input, streams)
