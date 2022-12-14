import argparse
import os
import shutil
import subprocess
from distutils import dir_util
from pathlib import Path

TEMPLATE_DIR = Path(__file__).parent / "project"


def parse_args():
    parser = argparse.ArgumentParser(description="config_file")
    parser.add_argument("-p", "--project", type=str)
    parser.add_argument("-d", "--dependencies", action="store_true", default=False)
    parser.add_argument("-l", "--localization", type=str)
    args = parser.parse_args()
    return args.project, args.dependencies, args.localization


def get_project_dir(project_path):
    for item in project_path.iterdir():
        if item.is_dir() and item.name not in ("tests",
                                               ".idea",
                                               "logs",
                                               "media",
                                               "static",
                                               "templates",
                                               "venv",
                                               "__pycache__",
                                               "backup",
                                               ".git"):
            return item


def create_setting_files(project_path: Path, project_name: str):
    for file in (".gitignore", "config.yaml", "config_dev.yaml", "README.md"):
        shutil.copy(TEMPLATE_DIR / file, project_path / file)
        file_path = project_path / file
        data = file_path.read_text(encoding="utf-8").replace("crying", project_name)
        file_path.write_text(data, encoding="utf-8")


def set_project_name_in_files(workdir: Path, project_name: str):
    for elem in workdir.iterdir():
        if elem.is_dir():
            if elem.name not in ("__pycache__",):
                set_project_name_in_files(elem, project_name)
            else:
                print(f"❌ {elem}")
        else:
            if elem.suffix != ".pyc":
                data = elem.read_text(encoding="utf-8")
                if elem.name == 'config.py':
                    data = data.replace("project/crying", project_name) \
                        .replace('project.crying', project_name) \
                        .replace('crying', project_name)
                else:
                    data = data.replace("project.crying", project_name)
                print(f"✅ {elem}")
                elem.write_text(data, encoding="utf-8")
            else:
                print(f"❌ {elem}")


def install_dependencies(project_path: Path):
    aiogram_version = 'aiogram@latest -E i18n --allow-prereleases'
    dependencies = ["loguru",
                    "pydantic",
                    "tortoise-orm[asyncpg]",
                    "pyyaml",
                    "APScheduler",
                    "cachetools",
                    "glQiwiApi",
                    "apscheduler",
                    "fluent-runtime"]

    dependencies = " ".join(dependencies)
    os.system(f"cd {project_path} && "
              f"poetry add {aiogram_version} && "
              f"poetry add {dependencies} && "
              f"poetry add git+https://github.com/taimast/aiogram-admin.git")


def init_localize(project_name: str, localization: str):
    os.system(f"pybabel extract ./{project_name}/ -o ./{project_name}/apps/bot/locales/{project_name}.pot")
    os.system(
        f"pybabel init -i ./{project_name}/apps/bot/locales/{project_name}.pot "
        f"-d ./{project_name}/apps/bot/locales/ -D {project_name} -l {localization}")


def main():
    # subprocess.Popen(['poetry', 'show', '--tree'])
    project_path, dependencies, localization = parse_args()
    if not project_path:
        permission = input("Путь до проекта не указан, установить в текущую директорию? [y/n]: ")
        if permission == "y":
            project_path = Path.cwd()
        else:
            exit("Укажите путь до проекта через аргумент -p")

    project_path = Path(project_path)
    if not project_path.exists():
        permission = input(f"Директория {project_path} не существует, создать как новый проект? [y/n]: ")
        if permission == "y":
            subprocess.Popen(['poetry', 'new', str(project_path)]).wait()
            print("✅ Проект создан")
        else:
            exit("❌ Проект не создан. Укажите путь до проекта через аргумент -p")

    print(f"Настройка проекта {project_path}.")
    workdir: Path = get_project_dir(project_path)
    project_name = workdir.name
    print(workdir)
    create_setting_files(project_path, project_name)
    print("Файлы настроек созданы")

    dir_util.copy_tree(str(TEMPLATE_DIR / "crying"), str(workdir))
    set_project_name_in_files(workdir, project_name)
    print("Шаблон настроен")

    if dependencies:
        print(f"Установка базовых зависимостей...")
        install_dependencies(project_path)

    if localization:
        init_localize(workdir.name, localization)


if __name__ == "__main__":
    main()
