from soccer_robot.module.module import Module
from soccer_robot.constants import MODULEMANAGER_MAX_TERM_TIME

from soccer_robot.logger.logger_module import LoggerModule

import time

# DISCLAIMER: ModuleManager should always stop all the modules before raising error, otherwise
# other processes may continue running even when the main process terminates 

class ModuleManager:
    def __init__(self) -> None:
        self._modules = []
        self._terminating_modules = []

        if not LoggerModule.is_inited():
            raise RuntimeError("ModuleManager cannot be instantiated without 'LoggerModule' being inited first")

        LoggerModule.launch() 

    # Should be called in the main application update
    def update(self) -> bool:
        self._check_for_termination()

        for i in self._modules:
            if (i.has_failed()):
                return False
        # Modules dependencies test, ...

        return True

    # Wait for all modules processes to stop and then terminates itself 
    def terminate(self) -> None:
        self.stop_modules()
        while True:
            if not self.is_some_module_running():
                break
            self._check_for_termination()
        
        LoggerModule.stop()

    def push_module(self, module) -> None:
        if not self._is_valid_module(module):
            LoggerModule.log_error("ModuleManager: Cannot push '{}', it is not inharited class of Module".format(str(module)))
            return

        if not module.is_inited():
            LoggerModule.log_error("ModuleManager: Cannot push '{}', it is not inited".format(module.module_name))
            return

        for i in self._modules:
            if i == module:
                LoggerModule.log_error("ModuleManager: Cannot push '{}', it is already pushed".format(module.module_name))
                return

        self._modules.append(module)

    def remove_module(self, module) -> None:
        if not self._is_valid_module(module):
            LoggerModule.log_error("ModuleManager: Cannot remove '{}', it is not inharited class of Module".format(str(module)))
            return

        if module in self._modules:
            module.stop()
            self._modules.remove(module)
        else:
            LoggerModule.log_error("ModuleManager: Cannot remove '{}', module not found".format(module.module_name))

    def start_module(self, module) -> None:
        if not self._is_valid_module(module):
            LoggerModule.log_error("ModuleManager: Cannot start '{}', it is not inharited class of Module".format(str(module)))
            return

        if module in self._modules:
            if not module.is_active():
                module.launch()
                LoggerModule.log_info("ModuleManager: Starting '{}' ({})".format(module.module_name, module.get_pid()))
        else:
            LoggerModule.log_error("ModuleManager: Cannot start '{}', module not found".format(module.module_name))

    def stop_module(self, module) -> None:
        if not self._is_valid_module(module):
            LoggerModule.log_error("ModuleManager: Cannot stop '{}', it is not inharited class of Module".format(str(module)))
            return

        if module in self._modules:
            if module.is_active():
                LoggerModule.log_info("ModuleManager: Stopping '{}'".format(module.module_name))
                module.stop()
                self._terminating_modules.append((module, time.time()))
        else:
            LoggerModule.log_error("ModuleManager: Cannot stop '{}', module not found".format(module.module_name))

    def start_modules(self) -> None:
        for i in self._modules:
            if not i.is_active():
                i.launch()
                LoggerModule.log_info("ModuleManager: Starting '{}' ({})".format(i.module_name, i.get_pid()))

    def stop_modules(self) -> None:
        for i in self._modules:
            LoggerModule.log_info("ModuleManager: Stopping '{}'".format(i.module_name))
            i.stop()
            self._terminating_modules.append((i, time.time()))

    def log_modules(self) -> None:
        log_message = "ModuleManager-Modules:"
        for i in self._modules:
            log_message += " {} ({}),".format(i.module_name, "Active" if i.is_active() else "Idle")
        LoggerModule.log_info(log_message)

    def is_some_module_running(self) -> bool:
        for i in self._modules:
            if i.is_active():
                return True
        
        return False

    def _is_valid_module(self, module) -> bool:
        return type(module) == type and issubclass(module, Module)

    def _check_for_termination(self) -> None:
        for i in self._terminating_modules:
            if i[0].is_active():
                if time.time() - i[1] > MODULEMANAGER_MAX_TERM_TIME:
                    i[0].terminate()
                    self._terminating_modules.remove(i)
                    LoggerModule.log_warning("ModuleManager: '{}' was not responding and was force terminated".format(i[0].module_name))
            else:
                self._terminating_modules.remove(i)
                continue
