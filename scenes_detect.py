import os
import subprocess
import datetime
import argparse

def check_nvidia_gpu():
    try:
        result = subprocess.run(['nvidia-smi'], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        return result.returncode == 0
    except FileNotFoundError:
        return False

def format_time(seconds):
    td = datetime.timedelta(seconds=round(seconds, 3))
    zero = datetime.datetime(1900,1,1)
    td = td + zero
    return td.strftime("%H:%M:%S.%f")[:-3]

def ffmpeg_detect(input_video, output_path=None, frame_rate=None, no_nv=False):
    video_dir = os.path.dirname(input_video)
    video_basename = os.path.splitext(os.path.basename(input_video))[0]
    
    os.chdir(video_dir)
    scenes_file = os.path.join(output_path or '', f'{video_basename}_scenes.txt')
    chapters_file = os.path.join(output_path or '', f'{video_basename}_chapters.txt')
    
    # Check for Nvidia GPU and set hardware acceleration flag if available and not skipped
    hwaccel_flag = ' -hwaccel cuda' if not no_nv and check_nvidia_gpu() else ''

    # Set frame rate flag if provided
    framerate_flag = f' -r {frame_rate}' if frame_rate else ''
    
    # Run ffmpeg command to detect scenes
    # https://ffmpeg.org/ffmpeg-filters.html#select_002c-aselect
    ffmpeg_command = f'ffmpeg -hide_banner{hwaccel_flag}{framerate_flag} -i "{input_video}" -map 0:v -vf "select=\'gt(scene,0.2)\',metadata=print:file={scenes_file}" -f null -'
    print(f"Running command: {ffmpeg_command}")
    subprocess.run(ffmpeg_command, shell=True, check=True)
    print(f"Scenes detection completed. Written to {scenes_file}")

    # Read scenes file and generate chapters file
    with open(scenes_file, 'r') as scenes, open(chapters_file, 'w') as chapters:
        chapter_index = 1
        for line in scenes:
            if 'pts_time' in line:
                pts_time_str = line.split('pts_time:')[1].strip()
                chapter_time = format_time(float(pts_time_str))
                chapters.write(f'CHAPTER{chapter_index:04d}={chapter_time}\n')
                chapters.write(f'CHAPTER{chapter_index:04d}NAME=Chapter {chapter_index:04d}\n')
                chapter_index += 1
    print(f"Chapter file created at {chapters_file}")

def rpu_convert(input_scenes, output_path=None, fps=None):
    """
    [dovi_tool](https://github.com/quietvoid/dovi_tool)

    dovi_tool export -i video_rpu.bin -d scenes=scenes.txt
    """
    scenes_dir = os.path.dirname(input_scenes)
    scenes_basename = os.path.splitext(os.path.basename(input_scenes))[0]
    chapters_file = os.path.join(output_path or scenes_dir, f'{scenes_basename}_chapters.txt')

    with open(input_scenes, 'r') as scenes, open(chapters_file, 'w') as chapters:
        chapter_index = 1
        for frame in scenes:
            chapter_time = format_time( int(frame) / float(fps) )
            chapters.write(f'CHAPTER{chapter_index:04d}={chapter_time}\n')
            chapters.write(f'CHAPTER{chapter_index:04d}NAME=Chapter {chapter_index:04d}\n')
            chapter_index += 1
    print(f"Chapter file created at {chapters_file}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Detect scenes and create OGG chapters file.')
    parser.add_argument('-i', '--input', required=True, help='Input file path (video or RPU scenes txt)')
    parser.add_argument('-o', '--output', help='Output directory for scenes and chapters files')
    parser.add_argument('-f', '--framerate', help='Assume the frame rate or the video frame rate will be used (e.g. 24, 24000/1001, 23.976, etc.)')
    parser.add_argument('--no-nv', action='store_true', help='Disable Nvidia GPU acceleration (video input only)')
    args = parser.parse_args()
    
    # Check if input is a file
    if not os.path.isfile(args.input):
        raise ValueError(f"The input path {args.input} is not a valid file.")
    
    # Check if output is a directory, if provided
    if args.output and not os.path.isdir(args.output):
        raise ValueError(f"The output path {args.output} is not a valid directory.")
    
    # Determine workflow
    if args.input.lower().endswith('.txt'):
        if args.framerate is None:
            raise ValueError("Frame rate (-f/--framerate) is required for RPU scenes txt")
        rpu_convert(args.input, args.output, args.framerate)
    else:
        ffmpeg_detect(args.input, args.output, args.framerate, args.no_nv)