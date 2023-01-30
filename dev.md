
https://docs.pytest.org/en/7.1.x/explanation/goodpractices.html#src-layout

```sh

source /opt/mambaforge/etc/profile.d/conda.sh
```


## License
`# SPDX-License-Identifier: MIT`

### Create
#mamba env create  -f environment.yaml


### Activate

```sh
env_name=rhubarb
conda activate $env_name
export MY_EXTRA_PROMPT1="($env_name)"
zsh
```

### Update

```sh
conda activate $env_name
mamba env update -f environment.yaml --prune

```

### Win
Install: https://mamba.readthedocs.io/en/latest/installation.html#windows
set MAMBA_ROOT_PREFIX=r:\mm

micromamba shell init -s cmd.exe -p R:\mambaPrefix
micromamba shell hook --shell=cmd.exe
micromamba env list
micromamba create -f environment.yaml
micromamba activate rhubarb

r:\mambaPrefix\Scripts\activate

## Vs Code

### Pylance

```json
    "python.analysis.diagnosticSeverityOverrides": {
        "reportOptionalMemberAccess": "none",
    }
```

### bpy modules

Fake bpy modules (seems more complete)
```json
    "python.autoComplete.extraPaths": [
        "/data/src/Blender/fake_bpy_modules_3.3-20221006"
    ],
    "python.analysis.extraPaths": [
        "/data/src/Blender/fake_bpy_modules_3.3-20221006"
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

Icons:
https://wilkinson.graphics/blender-icons/

Best practice:
https://docs.blender.org/api/current/info_best_practice.html


## Todo

* Add [speaker](https://docs.blender.org/manual/en/latest/render/output/audio/speaker.html) as an alternative to Sequencer audio clip
* Set start frame?
* Addd audio-sccrubbling checkbox
* Rename capture_panel to something better? (sound setup?)
* Extended cues check-box
* Rel/Abd path - make them prefix-small icons in from of the sound directory selector?

```
if not bpy.data.is_saved:
            self.relative = False
if self.relative:
            try:  # can't always find the relative path (between drive letters on windows)
                image.filepath = bpy.path.relpath(image.filepath)
            except ValueError:
                pass

```            