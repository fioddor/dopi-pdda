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
docker build -f .devcontainer/Dockerfile -t dopi-pdda-devcontainer:latest .
docker run --detach --name dopi-pdda-dev               \
           --volume $PWD:/workspace                    \
           --volume <path-to-shared-data-folder>:/data \
           dopi-pdda-devcontainer:latest
 
docker exec -ti dopi-pdda-dev bash      # develop inside the container
                                        # ...
exit                                    # exit the container when development is done

Inside the container:

```shell
pip install --user debian_observer   # the platform, as a library
pip install --user -e '.[dev]'       # the plug-in, editable
pytest tests/ -q                     # the battery
```

## Docker image hygiene

Manual devcontainer builds (docker build / devcontainer up --build)
re-tag the same name on every iteration and leave the previous run
dangling (<none> in docker images). The CI pipelines prune their own
dangling images at teardown, but manual sessions do not.

After a manual build session on a shared host, prune the dangling
images you left behind:

```shell
docker image prune -f   # removes ONLY untagged (<none>) images
```

Every manual rebuild leaks ~2.5 GB to the shared daemon otherwise
(the devcontainer image is the fat one). Check the accumulation
with docker system df and keep it flat.

