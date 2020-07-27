from inspect import getmembers, isfunction
from math import inf
from os.path import exists, join
from typing import Any, Iterator, Optional, Sequence

from ..clients import around, buffers, lsp, paths, tmux, tree_sitter
from ..shared.da import load_json, load_module, merge_all
from ..shared.types import Factory, Seed
from .consts import load_hierarchy, module_entry_point, settings_json
from .types import FuzzyOptions, Settings, SourceFactory, SourceSpec


def load_source(config: Any) -> SourceSpec:
    spec = SourceSpec(
        main=config["main"],
        short_name=config["short_name"],
        enabled=config["enabled"],
        limit=config.get("limit"),
        timeout=config.get("timeout"),
        config=config.get("config"),
    )
    return spec


def initial(configs: Sequence[Any]) -> Settings:
    config = merge_all(load_json(settings_json), *configs)
    fuzzy_o = config["fuzzy"]
    fuzzy = FuzzyOptions(min_match=fuzzy_o["min_match"],)
    sources = {name: load_source(conf) for name, conf in config["sources"].items()}
    settings = Settings(fuzzy=fuzzy, sources=sources)
    return settings


def load_external(spec: SourceSpec) -> Optional[Factory]:
    for path in load_hierarchy:
        candidate = join(path, spec.main)
        if exists(candidate):
            mod = load_module(candidate)
            for member_name, func in getmembers(mod, isfunction):
                if member_name == module_entry_point:
                    return func
    return None


def assemble(spec: SourceSpec, name: str, main: Factory) -> SourceFactory:
    limit = spec.limit or inf
    timeout = (spec.timeout or inf) / 1000
    config = spec.config or {}
    seed = Seed(config=config, limit=limit, timeout=timeout)
    fact = SourceFactory(
        name=name,
        short_name=spec.short_name,
        limit=limit,
        timeout=timeout,
        seed=seed,
        manufacture=main,
    )
    return fact


def load_factories(settings: Settings) -> Iterator[SourceFactory]:
    intrinsic = {
        around.NAME: around.main,
        buffers.NAME: buffers.main,
        lsp.NAME: lsp.main,
        paths.NAME: paths.main,
        tmux.NAME: tmux.main,
        tree_sitter.NAME: tree_sitter.main,
    }
    for name, main in intrinsic.items():
        spec = settings.sources[name]
        yield assemble(spec, name=name, main=main)

    for name, spec in settings.sources.items():
        if name not in intrinsic:
            main = load_external(spec)
            if main:
                yield assemble(spec, name=name, main=main)
