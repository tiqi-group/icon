def in_notebook() -> bool:
    return "__IPYTHON__" in globals()
