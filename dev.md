
https://docs.pytest.org/en/7.1.x/explanation/goodpractices.html#src-layout

```sh

source /opt/mambaforge/etc/profile.d/conda.sh
```

https://github.com/DanielSWolf/rhubarb-lip-sync

## License
`# SPDX-License-Identifier: MIT`

## Conda

### Create

Create blank env with only python/pip.

```sh
mamba create -n rhubarb -c conda-forge python=3.10 pip~=22.2 
```

Then Activate and Update the env (see below)
Note it seems it has to be done in two steps. Since the base(system) python and pip would have been used to install the dependencies instead.

### Activate

```sh
conda activate rhubarb
which python # Verify it points somewhere like `.conda/envs`. Not to the system python.
```

### Update

Activate the env first. The `--prune` is only needed if deps. were removed/renamed. Note the  `-f environment.yml` is used implicitly.
```sh
mamba env update --prune
```

### Win
Install: https://mamba.readthedocs.io/en/latest/installation.html#windows

```sh
set MAMBA_ROOT_PREFIX=r:\mm

micromamba shell init -s cmd.exe -p R:\mambaPrefix
micromamba shell hook --shell=cmd.exe
micromamba env list
micromamba create -f environment.yaml
micromamba activate rhubarb

r:\mambaPrefix\Scripts\activate
```

## Release

- Verify the rhubarb binary versions+hashes are the latest version available
- `cd scripts`
- `python rhubarb_bin.py` to download rhubar binaries and verify the checksums. It would also deploy the correct binary to the /bin folder based on the current platform (linux/mac/win).
- `python package.py` to create zipped distributions for each platform.


## Vs Code
Probably the easiest is to run the `code` or `code-oss` from within the activated conda env.
Then run `Python: Select Interpreter` and select the one from conda env.

### Pylance

```json
    "python.analysis.diagnosticSeverityOverrides": {
        "reportOptionalMemberAccess": "none",
    }
```

Already in `project.toml`. To add to the settings.json manually:
```json
 "python.formatting.provider": "black",
 "python.formatting.blackArgs": ["--line-length", "160", "--skip-string-normalization"],
 "python.formatting.blackPath": "/bin/black",
```

### bpy modules

[Fake bpy modules](https://github.com/nutti/fake-bpy-module) (seems more complete)
```json
    "python.autoComplete.extraPaths": [
        "/data/src/fake_bpy_modules_3.4-20230117"
    ],
    "python.analysis.extraPaths": [
        "/data/src/fake_bpy_modules_3.4-20230117"
    ],
```

Official bpy from pip:
```json
"python.autoComplete.extraPaths": [
        "/home/premik/.conda/envs/rhubarb/lib/python3.10/site-packages/bpy/3.4/scripts/modules/"
    ],
    "python.analysis.extraPaths": [
        "/home/premik/.conda/envs/rhubarb/lib/python3.10/site-packages/bpy/3.4/scripts/modules/"
    ],
```

Debug: https://github.com/JacquesLucke/blender_vscode
https://marketplace.visualstudio.com/items?itemName=JacquesLucke.blender-development


## Blender

###
For operator bl_idname, the same naming conventions as in 2.7x remain
Registration: Menu, Panel, Header, UIList, Operator
`UPPER_CASE_{SEPARATOR}_mixed_case` The separator for each identifier is listed below:
* Header -> _HT_
* Menu -> _MT_
* Operator -> _OT_
* Panel -> _PT_
* UIList -> _UL_

Valid Examples:
* `class OBJECT_OT_fancy_tool (and bl_idname = "object.fancy_tool")`
* `class MyFancyTool (and bl_idname = "MYADDON_MT_MyFancyTool")`
* `class SOME_HEADER_HT_my_header`
* `class PANEL123_PT_myPanel (lower case is preferred but mixed case is supported).`

https://wiki.blender.org/wiki/Reference/Release_Notes/2.80/Python_API/Addons#Registration

bpy.ops.sound.open(filepath='/tmp/work/1.ogg')

Uilist:
https://blender.stackexchange.com/questions/30444/create-an-interface-which-is-similar-to-the-material-list-box/30446#30446
https://blender.stackexchange.com/questions/8699/what-ui-would-work-for-choosing-from-a-long-long-list
https://blender.stackexchange.com/questions/717/is-it-possible-to-print-to-the-report-window-in-the-info-view

https://blender.stackexchange.com/questions/44356/fighting-split-col-and-aligning-row-content
https://sinestesia.co/blog/tutorials/using-uilists-in-blender/

Icons:
https://wilkinson.graphics/blender-icons/

Best practice:
https://docs.blender.org/api/current/info_best_practice.html


Properties
https://docs.blender.org/api/blender_python_api_master/bpy.props.html?highlight=floatproperty#get-set-example

## Todo

### High
* Set the panel tab name in the preferences

### Baking
* Add strip options: 
 - strips overlap start/end frames count
 - min/max stretch % to. Allow too short actions play faster and visa versa
 - (auto)interleaving,
* Autotrim strips, so they won't clash failing the bake
* Shape-key actions are not baked
* Doc - new readme.md

### Normal
* Add some simply blender sample file
* extended shapes- seems they are generated even when disabled -check
* Capture doesn't work for long sound files. Rhubarb finishes but the list is empty.
* limit number of lines in the result log dialog, to something like 100 (don't show more)

### Low
* Limit possible selection to armature and mesh-object only? (and not obj.library).
* Add [speaker](https://docs.blender.org/manual/en/latest/render/output/audio/speaker.html) as an alternative to Sequencer audio clip
* Rename capture_panel to something better? (sound setup?)
* The scaled down icons (32x32) still hard to see. Pre-scale different set icons?
* autoload - complete type-hints
* Capture panel, optimize, store pref, props etc. directy on the self (same like self.ctx)
* Verify the Dialog file is working
* Add "null" cue type to indicate un-detected cues (those red longer than the limit)
* `layout.prop(mlp, "actions_multiline_view") ` doesn't currently work. Should show regular action and shape-key action on two lines
* Not possible to un-select NLA track in the bake-panel


## Action selector
- only from the selected object?
- asset/nonasset
- shapekey/action
- armature actions only?
- match by name sub-string/regexp
- match by action group?


## Check
https://github.com/Hunanbean/Papagayo-NGLipsyncImporterForBlender

## Baking

My current thoughts about the baking is there should eventually be multiple options how to "bake" the captured mouth `Cues`:

1) To a new `Action`. Pretty much what is in the current version. Mapping setup requires creating an `Action` for each `Cue type`. And the result is a new `Action`. With each mouth-shape of the caputred `Cues` baked to key-frames.
2) To `NLA tracks`. The mouth-shape `Actions` and/or `Shapekey Actions` are put into two `NLA tracks` as `NLA strips` in a zig/zag pattern. With proper `strip` settings they'd get blended automatically by `NLA`. So Mapping setup requires creating `Actions` and/or `Shape-key Actions` (or both).
3) "Jump to frame" - more like a preview. Clicking on the captured `Cue` from the list would jump to the frame of  that Cue. This is inspired by the `Faceit` plugin. Where Every 10 frames there is different mouth shape (and optionally shape-key) keyframed directly on the timeline.

I also realized it doesn't make sense mark the Mouth-shape Actions as Assets. Like it is currently required in the PR. They can be makred as assets but it should't be required.

So from the use-case perspective, it makes more sense to split the whole process into two stages (two panels):
1 - **Sound setup and capture**: Select the sound input, run the binary. Captured cues are put into an `UIList` but not "baked" yet.
2 - **Cues mapping setup and baking**: For each `Cue type` an `Action` or/and `Shapekey Action` or frame number is provided (=the Mapping setup). Then baking is ran. While the baking can be run repeatidly without re-runing the capture.

So these thought led me to start working on this plugin more. But it took me more time than I anticipated and it ended up in a rewrite.

Currently I have the first part "Setup and Capture" is pretty much done on [my branch](https://github.com/Premik/blender-rhubarb-lipsync/tree/rework). But the mapping setup and baking the cues is still WIP.


https://blender.stackexchange.com/questions/206231/how-can-i-make-an-object-use-its-animation-action-at-a-specific-frame-in-blende


## NLA

NLA object tracks:

```python
[t.name for t in C.object.animation_data.nla_tracks]
```

NLA shape-key tracks:

```python
[t.name for t in C.object.data.shape_keys.animation_data.nla_tracks]
```
