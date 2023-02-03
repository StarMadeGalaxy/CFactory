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
import shutil
import platform
import hashlib
import json


class CFactory:
    def __init__(
        self, compiler: str = "clang++", 
        build_dir_name: str = "build", compiler_opts=list()):
        
        self.project_root_path = os.path.dirname(os.getcwd())
        self.project_name = CFactory.get_last_name_path(self.project_root_path)

        self.json_cache_file_name = "cfactory_sha256.json"
        self.json_cache_file_path = os.path.join(os.getcwd(), self.json_cache_file_name)

        self.build_dir_name = build_dir_name
        self.build_dir_path = os.path.join(self.project_root_path, self.build_dir_name)

        self.current_platform = platform.system()

        self.static_libs = list()
        self.dynamic_libs = list()

        self.compiler = compiler
        self.build_command: list = [compiler, "-o"]

        self.executable_name = self.project_name.lower()

        CFactory.insert_after(self.build_command, self.compiler, compiler_opts)

    def run(self):
        what_to_run = os.path.join(self.build_dir_path, self.executable_name)
        subprocess.call([what_to_run])
        
    def build(
            self, to_build: bool = True, delete_intermediate: bool = False, 
            print_command: bool = False, update_cache: bool = False, extension: str = "cpp",
            compile_without_linking_only: bool = False, remove_cache: bool = False):

        if update_cache:
            self.__update_cache(extension=extension)

        all_files_hash = dict(CFactory.get_files_dict_sha256(self.project_root_path, extension))
        loaded_hash = dict(CFactory.load_files_cache(self.json_cache_file_path))
        changed_files = list(CFactory.get_changed_files(all_files_hash, loaded_hash))

        clang_libs_name = list()
        
        if self.current_platform == "Windows":
            self.dynamic_libs += list(CFactory.find_files(self.project_root_path, "dll"))
            self.static_libs += list(CFactory.find_files(self.project_root_path, "lib"))
            print("Dynamic libs:", self.dynamic_libs)
            self.__copy_files_to_dir(self.dynamic_libs, self.build_dir_path)
            clang_libs_name = [lib for lib in self.static_libs]
            self.executable_name += ".exe"
        elif self.current_platform == "Linux": 
            self.dynamic_libs += list(CFactory.find_files(self.project_root_path, "so"))
            self.static_libs += list(CFactory.find_files(self.project_root_path, "a"))
            libs_directories = set(CFactory.find_files_dir(self.project_root_path, "so"))
            self.__dynamic_linker_search_libs_path(libs_directories)
            clang_libs_name = ["-l:" + CFactory.get_last_name_path(lib) for lib in self.dynamic_libs]
            self.executable_name += ".bin"

        CFactory.insert_after(self.build_command, "-o", [self.executable_name])
        CFactory.insert_after(self.build_command, self.executable_name, clang_libs_name)

        self.__goto_build_dir()
        self.__compile_without_linking(changed_files, print_command=print_command)

        print("All files hash:", all_files_hash)
        print("Loaded hash:", loaded_hash)
        print("Changed files: ", changed_files)
        
        if to_build and not compile_without_linking_only:
            object_files = list(CFactory.find_files(self.build_dir_path, "o"))
            print("Object files:", object_files)
            CFactory.insert_after(self.build_command, self.compiler, object_files)
            subprocess.call(self.build_command)
            
        if delete_intermediate:
            for file in object_files:
                os.remove(file)

        if remove_cache:
            self.__remove_cache()

        if print_command:
            self.__print_build_command()

    def __print_build_command(self):
        print("Build command:", *self.build_command)

    def __compile_without_linking(
        self, changed_files: list, to_build: bool = True, print_command: bool = False):
        clang_without_linking_flag = "-c"
        command = [self.compiler, clang_without_linking_flag]
        CFactory.insert_after(command, clang_without_linking_flag, changed_files)

        if print_command:
            print("Compile without linking command:", *command)

        if changed_files and to_build:
            subprocess.call(command)

    def __create_build_directory(self):
        build_dir_path = CFactory.find_build_dir(self.project_root_path, self.build_dir_name)

        if not build_dir_path:
            os.mkdir(self.build_dir_path)

    def __dynamic_linker_search_libs_path(self, pathes: set):
        dynamic_linker_rpath_list = ["-Wl", *["-rpath=" + path for path in pathes]]
        linker_comma_sep_args = ','.join(dynamic_linker_rpath_list)
        self.build_command += [linker_comma_sep_args]

    def __copy_files_to_dir(self, files: list, dir: str):
        for file in files:
            if not os.path.exists(file):
                shutil.copyfile(file, os.path.join(dir, CFactory.get_last_name_path(file)))

    def __open_build_directory(self):
        os.chdir(self.build_dir_path)

    def __goto_build_dir(self):
        self.__create_build_directory()
        self.__open_build_directory()

    def __remove_cache(self):
        if os.path.exists(self.json_cache_file_path):
            os.remove(self.json_cache_file_path)

    def __update_cache(self, extension: str):
        all_files_hash = CFactory.get_files_dict_sha256(self.project_root_path, extension)
        CFactory.dump_files_cache(self.json_cache_file_path, dict(all_files_hash))

    @staticmethod
    def get_changed_files(sources: dict, cache_dict: dict) -> list:
        if cache_dict:
            for file in sources:
                if (file not in cache_dict) or (sources[file] != cache_dict[file]):
                    yield file
        else:
            for file in sources:
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
    def get_files_dict_sha256(root: str, extension: str):
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

    # todo: several extensions check
    @staticmethod
    def find_files_dir(root: str, extension: str):
        for cur_dir, sub_dir, files in os.walk(root):
            for file in files:
                if fnmatch.fnmatch(file, f"*.{extension}"):
                    yield cur_dir

    @staticmethod
    def find_files(root: str, extension: str):
        for cur_dir, sub_dir, files in os.walk(root):
            for file in files:
                if fnmatch.fnmatch(file, f"*.{extension}"):
                    yield os.path.join(cur_dir, file)

    @staticmethod
    def insert_after(dest: list, element_after: str, sources: list):
        for source in reversed(sources):
            dest.insert(dest.index(element_after) + 1, source)
