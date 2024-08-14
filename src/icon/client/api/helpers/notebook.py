def in_notebook() -> bool:
    try:
        __IPYTHON__
        return True
    except NameError:
        return False
