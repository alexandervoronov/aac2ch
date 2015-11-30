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
    parser.add_argument('-p', '--podcast', dest='podcast',
                        default=False, action='store_true', help='Output only audiotrack.')
    parser.add_argument('-c', '--channels', dest='channels', type=int,
                        default=0, help='Number of channels in output audio.')
    parser.add_argument('--mono', dest='channels', action='store_const', const=1,
                        help='Convert audio to mono')
    parser.add_argument('--stereo', dest='channels', action='store_const', const=2,
                        help='Convert audio to stereo')
    
    return parser.parse_args()

def generate_temp_name(prefix, extension):
    dt_string = str(datetime.datetime.now())
    md5_obj = hashlib.md5()
    md5_obj.update(bytearray(dt_string, encoding='utf8'))
    random_string = md5_obj.hexdigest()
    return prefix + '_' + random_string + '.' + extension

def parse_stream_info(stream_line):
    stream_info = {}
    pattern = '^Stream #\d:\d(\((?P<lang>[a-z]{3})\))?: Audio: (?P<codec>[a-zA-Z0-9]{1,5})( [^,]*)?, .*?, (?P<channels>.*?),.*$'
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
    print(stream_info)
    lang_found = {single_stream['lang'] for single_stream in stream_info}
    lang_inter = lang_wanted.intersection(lang_found)
    filter_by_lang = len(lang_inter) > 0
    if filter_by_lang:
        stream_info = [single_stream for single_stream in stream_info
                                     if single_stream['lang'] in lang_inter]
    return stream_info

def get_ffmpeg_channels_param(channel_arg, stream_info):
    ffmpeg_channels = ''
    if channel_arg > 0:
        ffmpeg_channels = ' -ac {} '.format(channel_arg)
    if channel_arg == 0 and stream_info['channels'].find('5.1') != -1:
        ffmpeg_channels = ' -ac 2 '
    return ffmpeg_channels

def estimate_audio_gain(input_file, single_stream_info, cmd_args):
    ssi = single_stream_info

    rg_analyze_pattern = 'ffmpeg -hide_banner -i {0} -vn -sn -map 0:a:{1} -af "aresample=async=1" {2} -af "volumedetect" -f wav -y {3}'
    channel_setting = get_ffmpeg_channels_param(cmd_args.channels, ssi)
    rg_line = rg_analyze_pattern.format(input_file, ssi['index'], channel_setting, os.devnull)
    rg_proc = sarge.run(rg_line, stdout=sarge.Capture(), stderr=sarge.Capture())
    # print(rg_proc.stdout.text)
    maxvol_pattern = 'max_volume: -?([\d\.]+) dB'
    dbm = re.findall(maxvol_pattern, rg_proc.stderr.text)
    assert(len(dbm) == 1)
    result = float(dbm[0])
    return result

def encode_single_stream(cmd_args, stream, input_file, output_file):
    apply_gain = True

    # whole_pattern = 'ffmpeg -i {0} -vn -sn -map 0:a:{1} -af "aresample=async=1" {2} -f wav - | neroaacenc -q 0.xx -ignorelength -if - -of temp.m4a'
    ffmpeg_pattern = 'ffmpeg -hide_banner -i {0} -vn -sn -map 0:a:{1} -af "aresample=async=1" {2} {3} -f wav -'
    aac_pattern = 'neroaacenc -q 0.42 -ignorelength -if - -of {}'
    gain_pattern = ' -af "volume=+{0:.1f}dB" '

    if input_file.find(' ') != -1:
        input_file = '"{}"'.format(input_file)

    channel_setting = get_ffmpeg_channels_param(cmd_args.channels, stream)
    volume_setting = ''
    if apply_gain:
        gain = estimate_audio_gain(input_file, stream, cmd_args)
        volume_setting = gain_pattern.format(gain)
    ffmpeg_line = ffmpeg_pattern.format(input_file, stream['index'], channel_setting, volume_setting)
    aac_line = aac_pattern.format(output_file)
    print (ffmpeg_line)
    print (aac_line)
    sarge.run(ffmpeg_line + ' | ' + aac_line)

def generate_podcast_name(input_name):
    (base, ext) = os.path.splitext(input_name)
    result = base + '.m4a'
    if result == input_name:
        result = base + '_aac.m4a'
    return result

def encode_streams(input_file, stream_info, cmd_args):
    
    out_temp_files = []

    for stream in stream_info:
        if not cmd_args.podcast:
            tempname = generate_temp_name('stream{}'.format(stream['index']), 'm4a')
            stream['tempfile'] = tempname

            encode_single_stream(cmd_args, stream, input_file, tempname)
            out_temp_files.append(tempname)
        else:
            output_file = generate_podcast_name(input_file)
            encode_single_stream(cmd_args, stream, input_file, output_file)
    return out_temp_files

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
        print('Processing {}'.format(input_file, encoding='utf8'))
        streams = extract_audio_streams(input_file, args.lang)
        enc_streams = encode_streams(input_file, streams, args)
        if not args.podcast:
            mux_streams(input_file, enc_streams)
        delete_encoded_streams(enc_streams)
    print('Done.')

if __name__ == '__main__':
    run()
