# How to Contribute to Debian Observer

This is a personal project.

Feel free to contribute issues or pull requests.
Just don't expect me to react promptly.

# RoadMap

What and how I plan to develop is documented in `docs/`.
It is linked in README.md too.

This project is a plug-in of Debian Observer.
The contribution rules for the plug-in are the same from Debian Observer.

## Set Up a Development Environment

It is a good practice to separate the development environments from
each other and from your system.

The plug-in's devcontainer builds on the platform's images (the
plug-in develops against an installed platform, never against a
modified one). With the platform images present:

```shell
git clone https://ghostell.local/gitea/fioddor-dev/dopi-pdda.git
cd dopi-pdda
# open the .devcontainer in your container tooling, or:
docker run --rm -it -v $PWD:/workspace deb-obs-devcontainer:latest
```

Inside the container:

```shell
pip install --user debian_observer   # the platform, as a library
pip install --user -e '.[dev]'       # the plug-in, editable
pytest tests/ -q                     # the battery
```
