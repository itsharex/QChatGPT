import dulwich.porcelain


def update_all():
    try:
        from dulwich import porcelain
        repo = porcelain.open_repo('.')
        porcelain.pull(repo)
    except ModuleNotFoundError:
        raise Exception("dulwich模块未安装,请查看 https://github.com/RockChinQ/QChatGPT/issues/77")
    except dulwich.porcelain.DivergedBranches:
        raise Exception("分支不一致,自动更新仅支持master分支,请手动更新")
