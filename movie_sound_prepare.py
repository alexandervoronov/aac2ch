#!python3

# Script for batch conversion of 5.1 audio tracks to AAC 2.0.
# Requires ffmpeg, neroaacenc and mkvmerge.
#
# Special thanks to @slhck for explanation of audio gain ffmpeg options.

import argparse
import glob
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
    parser.add_argument('-l', '--lang', dest='lang', type=str,
                        default='eng', help='Filter audio tracks by language ("all" to keep all tracks).')
    
    return parser.parse_args()

def generate_temp_name(prefix, extension):
    dt_string = str(datetime.datetime.now())
    md5_obj = hashlib.md5()
    md5_obj.update(bytearray(dt_string, encoding='utf8'))
    random_string = md5_obj.hexdigest()
    return prefix + '_' + random_string + '.' + extension

def parse_stream_info(stream_line):
    stream_info = {}
    pattern = '^Stream #\d:\d(\((?P<lang>[a-z]{3})\))?: Audio: (?P<codec>[a-zA-Z0-9]{1,5}), .*?, (?P<channels>.*?),.*$'
    s_match = re.match(pattern, stream_line)
    keys = ['codec', 'lang', 'channels']
    print(stream_line)
    if s_match:
        stream_info = { key : s_match.group(key) for key in keys}
    return stream_info

def extract_audio_streams(input_file, lang):
    lang_wanted = set()
    if lang != 'all':
        lang_wanted = {lang, 'und'}
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

    # Apply filtering by language only if language is defined in stream info and
    # at least one stream is of wanted language.
    lang_found = {single_stream['lang'] for single_stream in stream_info}
    lang_inter = lang_wanted.intersection(lang_found)
    filter_by_lang = len(lang_inter) > 0
    if filter_by_lang:
        stream_info = [single_stream for single_stream in stream_info
                                     if single_stream['lang'] in lang_inter]
    return stream_info

def estimate_audio_gain(input_file, single_stream_info):
    ssi = single_stream_info
    ffmpeg_2ch = ' -ac 2 '

    rg_analyze_pattern = 'ffmpeg -hide_banner -i {0} -vn -sn -map 0:a:{1} -af "aresample=async=1" {2} -af "volumedetect" -f wav -y {3}'
    channel_setting = ffmpeg_2ch if ssi['channels'].find('5.1') != -1 else ''
    rg_line = rg_analyze_pattern.format(input_file, ssi['index'], channel_setting, os.devnull)
    rg_proc = sarge.run(rg_line, stdout=sarge.Capture(), stderr=sarge.Capture())
    # print(rg_proc.stdout.text)
    maxvol_pattern = 'max_volume: -?([\d\.]+) dB'
    dbm = re.findall(maxvol_pattern, rg_proc.stderr.text)
    assert(len(dbm) == 1)
    result = float(dbm[0])
    return result

def encode_streams(input_file, stream_info):
    apply_gain = True
    ffmpeg_2ch = ' -ac 2 '
    # whole_pattern = 'ffmpeg -i {0} -vn -sn -map 0:a:{1} -af "aresample=async=1" {2} -f wav - | neroaacenc -q 0.xx -ignorelength -if - -of temp.m4a'
    ffmpeg_pattern = 'ffmpeg -hide_banner -i {0} -vn -sn -map 0:a:{1} -af "aresample=async=1" {2} {3} -f wav -'
    aac_pattern = 'neroaacenc -q 0.42 -ignorelength -if - -of {}'
    gain_pattern = ' -af "volume=+{0:.1f}dB" '
    
    out_files = []
    if input_file.find(' ') != -1:
        input_file = '"{}"'.format(input_file)
    for stream in stream_info:
        tempname = generate_temp_name('stream{}'.format(stream['index']), 'm4a')
        stream['tempfile'] = tempname
        channel_setting = ffmpeg_2ch if stream['channels'].find('5.1') != -1 else ''
        volume_setting = ''
        if apply_gain:
            gain = estimate_audio_gain(input_file, stream)
            volume_setting = gain_pattern.format(gain)
        ffmpeg_line = ffmpeg_pattern.format(input_file, stream['index'], channel_setting, volume_setting)
        aac_line = aac_pattern.format(tempname)
        print (ffmpeg_line)
        print (aac_line)
        sarge.run(ffmpeg_line + ' | ' + aac_line)
        out_files.append(tempname)
    return out_files

def generate_output_name(input_name):
    (base, ext) = os.path.splitext(input_name)
    return base + '_aac.mkv'

def mux_streams(input_file, encoded_streams):
    mkv_pattern = 'mkvmerge -o "{0}" --no-audio "{1}"'
    mka_pattern = '--language 0:eng --no-chapters "{0}"'

    mkv_line = mkv_pattern.format(generate_output_name(input_file), input_file)
    audio_lines = [mka_pattern.format(single_stream) for single_stream in encoded_streams]
    mkv_line += ' ' + ' '.join(audio_lines)
    print(mkv_line)
    sarge.run(mkv_line)

def extract_input_list(input_mask):
    target = input_mask.replace('[', '[[]')
    return glob.glob(target)

def delete_encoded_streams(encoded_streams):
    for stream in encoded_streams:
        try:
            os.remove(stream)
        except Exception as e:
            print(e)

def run():
    args = parse_args()
    input_list = extract_input_list(args.input)
    for input_file in input_list:
        print('Processing {}'.format(input_file))
        streams = extract_audio_streams(input_file, args.lang)
        enc_streams = encode_streams(input_file, streams)
        mux_streams(input_file, enc_streams)
        delete_encoded_streams(enc_streams)
    print('Done.')

if __name__ == '__main__':
    run()
