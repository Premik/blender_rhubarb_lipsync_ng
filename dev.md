
https://docs.pytest.org/en/7.1.x/explanation/goodpractices.html#src-layout

```sh

source /opt/mambaforge/etc/profile.d/conda.sh
```


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
mamba env update -f environment.yaml
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

### Fake bpy modules
```json
    "python.autoComplete.extraPaths": [
        "/data/src/Blender/fake_bpy_modules_3.3-20221006"
    ],
    "python.analysis.extraPaths": [
        "/data/src/Blender/fake_bpy_modules_3.3-20221006"
    ],
```

Debug: https://github.com/JacquesLucke/blender_vscode



## Blender

### 
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
