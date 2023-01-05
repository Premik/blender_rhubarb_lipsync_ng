
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