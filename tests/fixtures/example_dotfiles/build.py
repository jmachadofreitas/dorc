from dorc import Build, create_dir, link, links, recipe, retired, same
from dorc.platform import darwin, linux


build = Build("fixture")

setup = build.flow("setup")


@setup.task(linux)
def setup_linux():
    return [recipe("setup")]


directories = build.flow("directories")


@directories.task
def common():
    return [create_dir("~/.config", "~/.local/bin")]


install = build.flow("install", default=True, after=[directories], dependencies="prompt")


@install.task
def common():
    return [
        links("dots", "~", {".gitconfig": "dot-gitconfig", ".tmux.conf": "dot-tmux.conf"}),
        link(retired("dot-inputrc"), ".inputrc", source_dir="dots", target_dir="~"),
    ]


@install.task(linux, after=common)
def linux_files():
    return [
        link("dot-bashrc", ".bashrc", source_dir="dots", target_dir="~"),
        link("dot-bash_profile", ".bash_profile", source_dir="dots", target_dir="~"),
    ]


@install.task(darwin, after=common)
def darwin_files():
    return [link("dot-zshrc", ".zshrc", source_dir="dots", target_dir="~")]


unlink_install = install.infer_unlink(command="unlink-install")
