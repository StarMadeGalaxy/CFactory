# This file is intended to run from the setup directory, folding level 1
#
# +project_root
# |
# +--+setup
#    |
#    +--+build.py

import subprocess
import fnmatch
import os
import platform
import hashlib
import json


class CFactory:
    def __init__(self, compiler="clang++", build_dir_name="build"):
        self.project_root_path = os.path.dirname(os.getcwd())
        self.project_name = CFactory.get_last_name_path(self.project_root_path)

        self.json_cache_file_name = "cfactory_sha256.json"
        self.json_cache_file_path = os.path.join(os.getcwd(), self.json_cache_file_name)

        self.build_dir_name = build_dir_name
        self.build_dir_path = os.path.join(self.project_root_path, self.build_dir_name)

        self.current_platform = platform.system()

        self.compiler = compiler
        self.build_command: list = [compiler, "-o"]
        self.compiler_opts = list()

    def build(
            self, to_build: bool = True, delete_intermediate: bool = False,
            print_command: bool = False, update_cache: bool = False, extension: str = "cpp",
            compile_without_linking_only: bool = False):

        if update_cache:
            self.__update_cache(extension=extension)

        all_files_hash = dict(CFactory.get_files_dict_sha256(self.project_root_path, extension))
        loaded_hash = CFactory.load_files_cache(self.json_cache_file_path)
        files_to_compile = list(CFactory.get_changed_files(all_files_hash, loaded_hash))

        cpp_sources = CFactory.find_files(self.project_root_path, extension)
        static_libs = ["-static"]
        dynamic_libs = list()
        executable_name = self.project_name
        # static_libs += CFactory.find_files(self.project_root_path, "so")

        if self.current_platform == "Windows":
            dynamic_libs = CFactory.find_files(self.project_root_path, "dll")
            static_libs += CFactory.find_files(self.project_root_path, "lib")
            executable_name += ".exe"
        elif self.current_platform == "Linux":
            dynamic_libs = CFactory.find_files(self.project_root_path, "so")
            executable_name += ".bin"

        CFactory.insert_after(self.build_command, "-o", [executable_name])
        CFactory.insert_after(self.build_command, self.compiler, cpp_sources)
        # CFactory.insert_after(self.build_command, executable_name, static_libs)

        if to_build:
            self.__goto_build_dir()
            self.__compile_without_linking(files_to_compile)
            object_files = CFactory.find_files(os.getcwd(), "o")
            self.build_command = [opt for opt in self.build_command if extension not in opt]
            CFactory.insert_after(self.build_command, self.compiler, object_files)

            if not compile_without_linking_only:
                subprocess.call(self.build_command)

            if delete_intermediate:
                for file in object_files:
                    os.remove(file)
        if print_command:
            self.__print_build_command()

    def __print_build_command(self):
        print("Build command:", self.build_command)

    def __compile_without_linking(
            self, files_to_compile: list, to_build: bool = True, print_command: bool = False):
        clang_without_linking_flag = "-c"
        command = [self.compiler, clang_without_linking_flag]
        CFactory.insert_after(command, clang_without_linking_flag, list(files_to_compile))

        if print_command:
            print("Compile without linking command:", files_to_compile)

        if files_to_compile:
            subprocess.call(command)

    def __create_build_directory(self):
        build_dir_path = CFactory.find_build_dir(self.project_root_path,
                                                 self.build_dir_name)
        self.build_dir_path = build_dir_path

        if not build_dir_path:
            os.mkdir(build_dir_path)

    def __open_build_directory(self):
        os.chdir(self.build_dir_path)

    def __goto_build_dir(self):
        self.__create_build_directory()
        self.__open_build_directory()

    def __remove_cache(self):
        if os.path.exists(self.json_cache_file_path):
            os.remove(self.json_cache_file_path)

    def __update_cache(self, extension: str):
        all_files_hash = dict(CFactory.get_files_dict_sha256(self.project_root_path, extension))
        CFactory.dump_files_cache(self.json_cache_file_path, all_files_hash)

    @staticmethod
    def get_changed_files(sources: dict, cache_dict: dict):
        for file in sources:
            if file not in cache_dict:
                yield file
            elif sources[file] != cache_dict[file]:
                yield file

    @staticmethod
    def get_last_name_path(path: str) -> str:
        return path.split(os.sep)[-1]

    @staticmethod
    def find_build_dir(root: str, build_dir_name: str) -> str:
        if build_dir_name in os.listdir(root):
            return os.path.join(root, build_dir_name)

    @staticmethod
    def load_files_cache(cache_file_path: str) -> dict:
        if os.path.exists(cache_file_path):
            with open(cache_file_path, 'r') as cache_file:
                return json.load(cache_file)
        return dict()

    @staticmethod
    def dump_files_cache(cache_file_path: str, files_hashes: dict):
        with open(cache_file_path, "w") as cache_file:
            json.dump(files_hashes, cache_file)

    @staticmethod
    def get_files_dict_sha256(root: str, extension: str) -> tuple:
        for file in CFactory.find_files(root, extension):
            yield file, CFactory.get_file_sha256(file)

    @staticmethod
    def get_file_sha256(file_path: str) -> str:
        hash_func = hashlib.sha256()
        with open(file_path, "rb") as read_file:
            while True:
                data_chunk = read_file.read(hash_func.block_size)
                hash_func.update(data_chunk)
                if not data_chunk:
                    break
        return hash_func.hexdigest()

    @staticmethod
    def find_files(root: str, extension: str) -> list:
        for cur_dir, sub_dir, files in os.walk(root):
            for file in files:
                if fnmatch.fnmatch(file, f"*.{extension}"):
                    yield os.path.join(cur_dir, file)

    @staticmethod
    def insert_after(dest: list, element_after: str, sources: list):
        for source in sources:
            dest.insert(dest.index(element_after) + 1, source)


def main():
    builder = CFactory()
    builder.build(to_build=True, print_command=True)


if __name__ == "__main__":
    main()
