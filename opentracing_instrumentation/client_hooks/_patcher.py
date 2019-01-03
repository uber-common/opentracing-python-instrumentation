class Patcher(object):

    def __init__(self):
        self.patches_installed = False

    @property
    def applicable(self):
        raise NotImplementedError

    def install_patches(self):
        if self.patches_installed:
            return

        if self.applicable:
            self._install_patches()
        self.patches_installed = True

    def reset_patches(self):
        if self.applicable:
            self._reset_patches()
        self.patches_installed = False

    def _install_patches(self):
        raise NotImplementedError

    def _reset_patches(self):
        raise NotImplementedError
