# renamer

A quick and dirty renaming utility for cleaning up the output of tools like
MakeMKV and [ARM][arm]. It helps you sensibly reorganize titles and ensure all
episodes are sequentially ordered across discs.

## Installation

Ensure you have the following installed:

 * Python 3.6 or newer
 * `ffprobe`

Then, run:

```bash
pip3 install git+https://github.com/timothyb89/renamer
```

Once installed, you can run it from anywhere:

```bash
renamer --help
```

If you'd prefer, you can also clone the repository and run it manually. Install
the requirements:
```bash
pip3 install -r requirements.txt
```

Then run it from cloned directory:

```bash
python3 renamer.py --help
```

## Usage

If you were to make a local backup of a series from discs, you might end up with
a directory structure like this:

```
Show Season 1 Disc 1/
  title_2.mkv   # an unwanted intro clip (3min)
  title_3.mkv   # an unwanted behind-the-scenes clip (26min)
  title_4.mkv   # E1 (43min)
  title_5.mkv   # E2 (42min)
  title_6.mkv   # E3 (45min)
  title_7.mkv   # E4 (44min)
  title_11.mkv  # an unwanted commentary track (44min)
Show Season 1 Disc 2/
  title_4.mkv   # E5 (45min)
  title_5.mkv   # E6 (44min)
  title_6.mkv   # E7 (43min)
  title_7.mkv   # E8 (44min)
Show Season 1 Disc 3/
  ... E9-11 ...
  title_4.mkv   # E9 (45min)
  title_5.mkv   # E10 (44min)
  title_6.mkv   # E11 (43min)
  title_7.mkv   # an unwanted commentary track (44min)

Show Season 2 Disc 1/
  ...

[...snip...]
```

Ideally we'd like to end up with a single directory for the entire season
containing only sensibly-named files like `S1E5.mkv`, which other tools can then
use to look up additional metadata.

Luckily for us, the episodes are in order (`title_N.mkv`) but there are various
clips we don't want. The ripping tool cleaned up a few of these but missed some
others. If we can trim them all out, we should be left with just the actual
episodes, in sequential order, which we can then number appropriately based on
their index.

By examining the episodes we can use `renamer` to help order and rename
these clips:
 * Several of the unwanted clips are unusually short (25min or less) compared
   to the normal episode length (44min).

   `renamer` determines the normal episode length and automatically skips
   unusually short clips. You can tune the automatic value using the
   `--confidence` flag where smaller values (e.g. 0.5 or lower) are more 
   restrictive and more likely to skip legitimate content.

   Alternatively, the calculated minimum can be overridden entirely using
   `--min-duration=30min` or similar.
 * Per the booklet that came with our discs, we know each disc has at most
   4 proper episodes.
    
   The `--exclude-after` flag can be used to set the maximum number of clips to
   keep in a particular directory. `--exclude-after=4
 * The last disc only has 3 episodes so the commentary track won't be excluded
   by any of the previous rules. We can exclude it manually using
   `--exclude '* 3/title_7.mkv`

`renamer` also lets you tune the output format:

 * `--input-regex` is matched against relative input paths and any captured
   groups are made available to `--output-format`.

   ```
   --input-regex 'Season (\d+) Disc (\d+)/.*'
   ```
   ...captures the season and disc numbers from the parent directory; they'll be available to the output formatter as `{0}` and `{1}` (or just `{} {}`).

   Named groups are also allowed:
   ```
   --input-regex 'Fringe Season (?P<season>\d+) Disc (?P<disc>\d+)/.*'
   ```
   These will be available as either `{0}` and `{1}` or as `{season}` and
   `{disc}`.
   
   Note that this flag can also be used as an additional filter; paths that
   don't match will be skipped.
 * `--output-format` controls the output filename (and subdirectory).
   
   It accepts a Python "new-style" format string; see https://pyformat.info/ for
   more detailed syntax info.

   A few variables come predefined:
    * `{index}`: the episode index starting from zero
    * `{offset_index}`: the episode index starting from 1
    * `{extension}`: the extension from the input file
    * ... plus any captured groups from the `--input-regex`, if set

   By default, it's `E{offset_index}{extension}`, which outputs `E1.mkv` ...
   `E12.mkv`, etc.
   
   If you capture the season and disc, you could use:

   ```
   --output-format 'S{season}D{disc}E{offset_index:02d}{extension}'
   ```

   ... to include everything and zero-pad the episode number.

Note: you can run `renamer` repeatedly to see which files are kept. It runs in
'dry-run' mode until you specify an output directory (`--output`).

[arm]: https://github.com/automatic-ripping-machine/automatic-ripping-machine

## License

MIT
