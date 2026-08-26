from pathlib import Path

import pytest

from dorc import Build, create_dir, links, recipe, retired, shell
from dorc.assets import Asset, Shell
from dorc.cli import main
from dorc.platform import Host, darwin, linux, ubuntu
from dorc.runtime import Planner, Runner, load_build

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests" / "fixtures" / "example_dotfiles" / "build.py"


def test_example_build():
    """The reference build exposes the intended flows and composed command."""
    build = load_build(ROOT / "examples" / "build.py").build

    assert [flow.name for flow in build.flows] == [
        "setup",
        "tools",
        "directories",
        "install",
        "unlink-install",
    ]
    assert [flow.name for flow in build.all_flow.after] == [
        "setup",
        "tools",
        "directories",
        "install",
    ]


def test_tasks():
    """Tasks select host assets and exclude desktop assets when headless."""
    build = Build("test")
    flow = build.flow("install", default=True)

    @flow.task
    def common():
        return [create_dir("~/.config"), create_dir("~/Applications", desktop=True)]

    @flow.task(ubuntu, after=common)
    def ubuntu_files():
        return [recipe("ubuntu")]

    host = Host("linux", "ubuntu")
    assert [task.name for task in flow.selected_tasks(host)] == [
        "common",
        "ubuntu_files",
    ]
    assert [asset.name for asset in flow.assets(host, desktop=False)] == [
        "~/.config",
        "ubuntu",
    ]
    assert [asset.name for asset in flow.assets(host, desktop=True)] == [
        "~/.config",
        "~/Applications",
        "ubuntu",
    ]


def test_task_order():
    """A task runs only after each task named in its ``after`` list."""
    build = Build("test")
    flow = build.flow("install", default=True)

    @flow.task
    def first() -> list[Asset]:
        return []

    @flow.task
    def second() -> list[Asset]:
        return []

    @flow.task(after=(first, second))
    def last() -> list[Asset]:
        return []

    assert [task.name for task in flow.selected_tasks(Host("linux", "ubuntu"))] == [
        "first",
        "second",
        "last",
    ]


def test_selected_task_dependencies():
    """A selected task cannot depend on a task excluded by host selection."""
    build = Build("test")
    flow = build.flow("install", default=True)

    @flow.task(darwin)
    def darwin_prerequisite() -> list[Asset]:
        return []

    @flow.task(ubuntu, after=darwin_prerequisite)
    def ubuntu_task() -> list[Asset]:
        return []

    with pytest.raises(
        ValueError, match="task cycle or unselected dependency in install"
    ):
        flow.selected_tasks(Host("linux", "ubuntu"))


def test_shell():
    """The public shell helper creates a shell-command asset."""
    asset = shell(name="hello", command="printf hello")

    assert isinstance(asset, Shell)
    assert asset.name == "hello"
    assert asset.command == "printf hello"


def test_flow_dependencies():
    """A flow can skip, prompt for, or run its predecessor flows."""
    build = Build("test")
    setup = build.flow("setup")
    tools = build.flow("tools", after=[setup], dependencies="prompt")
    clean = tools.infer_unlink(command="unlink-tools")
    planner = Planner()

    prompted_plan = planner.plan(tools)
    assert prompted_plan.prompted
    assert [flow.name for flow in prompted_plan.flows] == ["tools"]
    assert [flow.name for flow in planner.plan(tools, override="skip").flows] == [
        "tools"
    ]
    assert [flow.name for flow in planner.plan(tools, override="run").flows] == [
        "setup",
        "tools",
    ]
    assert [flow.name for flow in planner.plan(build.all_flow).flows] == [
        "setup",
        "tools",
    ]
    assert clean.name not in [flow.name for flow in build.all_flow.after]


def test_retired_links():
    """Retired links use their target name unless given an old source name."""
    removed = links("dots", "~", {"old": retired})[0]
    renamed = links("dots", "~", {"old": retired("new")})[0]

    assert (removed.source, removed.retired) == ("dots/old", True)
    assert (renamed.source, renamed.retired) == ("dots/new", True)


def test_install_and_unlink(tmp_path: Path):
    """An inferred unlink flow removes only links declared by its install flow."""
    loaded = load_build(FIXTURE)
    host = Host("linux", "ubuntu")
    runner = Runner(
        source_root=loaded.source_root, home=tmp_path, host=host, desktop=False
    )
    install = loaded.build.resolve("install")
    runner.run(Planner().plan(install, override="skip"))

    assert (tmp_path / ".bashrc").is_symlink()
    assert not (tmp_path / ".inputrc").exists()
    runner.run(Planner().plan(loaded.build.resolve("unlink-install")))
    assert not (tmp_path / ".bashrc").exists()


def test_status_dependencies(capsys):
    """Status reports prompted predecessors without asking for confirmation."""
    main(
        [
            "install",
            str(FIXTURE),
            "--status",
            "--platform",
            "linux",
            "--distro",
            "ubuntu",
        ]
    )

    assert "install depends on: directories" in capsys.readouterr().err


def test_list(capsys):
    """List accepts a build file without requiring a flow name."""
    assert main(["--list", str(FIXTURE)]) == 0

    assert capsys.readouterr().out.splitlines() == [
        "setup",
        "directories",
        "install",
        "unlink-install",
        "all",
    ]
