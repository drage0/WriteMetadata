#!/bin/env python3
#
# Embed chapter info and subtitles into a matroska file.
#

import os, sys, argparse, re, tempfile, subprocess;

class ChapterInfo:
    def __init__(self, second, milisecond, title):
        self.second     = second;
        self.milisecond = milisecond;
        self.title      = title;

    def TotalTime(self, timebase):
        return self.second*timebase + self.milisecond;

    def __str__(self):
        return f"\"{self.title}\" @ {self.second}s {self.milisecond}ms";

    def __repr__(self):
        return str(self);

class SubtitleInfo:
    def __init__(self, start_second, start_milisecond, end_second, end_milisecond, text):
        self.start_second     = start_second;
        self.start_milisecond = start_milisecond;
        self.end_second       = end_second;
        self.end_milisecond   = end_milisecond;
        self.text             = text;

    #
    # Beucase we are using .srt file format,
    # data is expected to be in HH:MM:SS,mmm foramt.
    #
    def FileData(self):
        data = [
            f"{self.start_second//3600}:{(self.start_second%3600)//60:02}:{self.start_second%60:02},{self.start_milisecond:03}",
            " --> ",
            f"{self.end_second//3600}:{(self.end_second%3600)//60:02}:{self.end_second%60:02},{self.end_milisecond:03}",
            "\n",
            self.text];
        return "".join(data);

    def __str__(self):
        return f"\"{self.text}\" @ {self.start_second}s {self.start_milisecond}ms --> {self.end_second}s {self.end_milisecond}ms";

    def __repr__(self):
        return str(self);

#
# Usage
#
def Usage(program):
    print(f"Usage: {program} [-h] -m (metadata file) -i (input matroska file) -o (output matroska file)");
    print("  -h: Display this help message");
    print("  -m: metadata file");
    print("  -i: Input matroska file");
    print("  -o: Output matroska file");

#
# Given text in format "HH:MM:SS.mmm", calculate total seconds and miliseconds.
# Only seconds (SS) are required, other parts can be ommitted.
# Milliseconds are filled with zeroes if there are not enough digits present.
#
def TimeSplit(timetext, timebase):
    split = timetext.split(".");

    milisecond = (int(split[1].ljust(3, '0')) if len(split) > 1 and split[1].isnumeric() else 0);

    segment      = split[0].split(":");
    second       = 0;
    segmentcount = len(segment);
    for i in range(segmentcount):
        multiplier = [1, 60, 60*60, 60*60*24][i];
        second += int(segment[segmentcount-i-1])*multiplier;

    return (second, milisecond);

#
# Main
#
def Main(argv, argc):
    TIMEBASE       = 1000;
    chapterlist    = [];
    subtitlelist   = [];
    subtitlelocale = "en_GB";

    parser = argparse.ArgumentParser();
    parser.add_argument("-m", "--metadata", help="metadata file");
    parser.add_argument("-i", "--input",    help="input matroska file");
    parser.add_argument("-o", "--output",   help="output matroska file");
    args = parser.parse_args();

    if args.metadata is None:
        print("Error: metadata file not specified");
        Usage(argv[0]);
        return 1;
    if args.input is None:
        print("Error: input matroska file not specified");
        Usage(argv[0]);
        return 2;
    if args.output is None:
        print("Error: output matroska file not specified");
        Usage(argv[0]);
        return 3;

    #
    # Read metadata file.
    # Chapters:
    #   3rd group contains the time, it has to be split at '.'.
    #   Because miliseconds are optional, check if it exists.
    #   Seconds are broken up into segments, each segment is multiplied by how many seconds that segment makes up.
    #

    with open(args.metadata, "r") as file:
        regex_chapter        = re.compile(r"(CHAPTER)(\s+)([0-9:.]+)(\s+)(.+)");
        regex_subtitle       = re.compile(r"(SUBTITLE)(\s+)([0-9:.]+)(\s+)([0-9:.]+)(\s+)(.+)");
        regex_subtitlelocale = re.compile(r"(SUBTITLELOCALE)(\s+)(.+)");
        regex_comment        = re.compile(r"\s*;(.*)");

        for line in file:
            if (match := regex_chapter.search(line)):
                second, millisecond = TimeSplit(match.group(3), TIMEBASE);
                title               = match.group(5).strip();
                chapterlist.append(ChapterInfo(second, millisecond, title));
            elif (match := regex_subtitle.search(line)):
                start_second, start_millisecond = TimeSplit(match.group(3), TIMEBASE);
                end_second,   end_millisecond   = TimeSplit(match.group(5), TIMEBASE);
                title                           = match.group(7).strip().replace("\\n", "\n");
                subtitlelist.append(SubtitleInfo(start_second, start_millisecond, end_second, end_millisecond, title));
            elif (match := regex_subtitlelocale.search(line)):
                subtitlelocale = match.group(3).strip();
            elif ((line.strip() == '') or (match := regex_comment.search(line))):
                pass;
            else:
                print(f"Error: Erroneous line - {line}", file=sys.stderr);
    
    for i, chapter in enumerate(chapterlist):
        print(f"Chapter {i+1}: {chapter}");
    for i, subtitle in enumerate(subtitlelist):
        print(f"Subtitle {i+1}: {subtitle}");

    #
    # Write metadata file.
    # Temporary file must be closed after writing is finished and be removed later!
    #

    try:
        temp_metadataname = tempfile.NamedTemporaryFile(mode="w", delete=False);

        print(f"Temporary file: {temp_metadataname.name}");
        for i in range(len(chapterlist)):
            chapter_now  = chapterlist[i];
            chapter_next = chapterlist[i+1] if i+1 < len(chapterlist) else None;

            time_start = chapter_now.TotalTime(TIMEBASE);
            time_end   = chapter_next.TotalTime(TIMEBASE) if chapter_next is not None else time_start;

            buffer  = f"[CHAPTER]\n";
            buffer += f"TIMEBASE=1/{TIMEBASE}\n";
            buffer += f"START={time_start}\n";
            buffer += f"END={time_end}\n";
            buffer += f"TITLE={chapter_now.title}\n";
            temp_metadataname.write(buffer);
        temp_metadataname.flush();
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr);
        return 4;
    temp_metadataname.close();

    try:
        temp_subtitlename = tempfile.NamedTemporaryFile(mode="w", delete=False);

        print(f"Temporary file: {temp_subtitlename.name}");
        for i, subtitle in enumerate(subtitlelist):
            buffer  = f"{i+1}\n";
            buffer += f"{subtitle.FileData()}\n";
            temp_subtitlename.write(buffer);
        temp_subtitlename.flush();
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr);
        return 5;
    temp_subtitlename.close();

    subprocess.run([
        "ffmpeg",
        "-hide_banner",
        "-loglevel", "warning",
        "-y",
        "-f", "matroska",   "-i", args.input,             # Input stream 0
        "-f", "ffmetadata", "-i", temp_metadataname.name, # Input stream 1
        "-f", "srt",        "-i", temp_subtitlename.name, # Input stream 2
        "-map",             "0",
        "-map",             "2:0",
        "-map_metadata",    "1",
        "-metadata:s:s:0",  f"language={subtitlelocale}",
        "-c:v", "copy",
        "-c:a", "copy",
        "-c:s", "copy",
        args.output]);

    print(f"Removing temporary files...");
    os.remove(temp_metadataname.name);
    os.remove(temp_subtitlename.name);

    print(f"Output file: {args.output}");

if __name__ == "__main__":
    argv = sys.argv;
    argc = len(argv);
    exit(Main(argv, argc));
