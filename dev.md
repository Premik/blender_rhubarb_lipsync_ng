
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
