# Upload 177
import datetime
import filecmp
import os
import random
import shutil
import sys
import time

import matplotlib.pyplot as plt
import networkx as nx
import tzlocal


PATH = os.getcwd()
WIT = ".wit"
IMAGES = "images"
STAGING = "staging_area"
ACTIVATED = "activated.txt"


class CheckoutError(Exception):
    pass


class BranchError(Exception):
    pass


class MergeError(Exception):
    pass


def init():
    for path in (WIT, os.path.join(WIT, IMAGES), os.path.join(WIT, STAGING)):
        try:
            full_path = os.path.join(PATH, path)
            os.mkdir(full_path)
        except FileExistsError:
            print(f"{full_path} already exists!")
    with open(os.path.join(PATH, WIT, ACTIVATED), "w") as file:
        file.write("master")


def find_wit(path):
    files = os.listdir(path)
    if WIT not in files:
        if os.path.dirname(path) == path:
            return
        return find_wit(os.path.dirname(path))
    return os.path.join(path, WIT)


def check_wit(f):
    def new_f(*args, **kwargs):
        wit = find_wit(PATH)
        if wit is None:
            raise FileNotFoundError(f"Can't start this function {f}. No wit exists in the given path")
        else:
            return f(*args, **kwargs)
    return new_f


def create_folders(path, destination):
    if os.path.dirname(path) == "":
        try:
            os.mkdir(os.path.join(destination, path))
        except FileExistsError:
            pass
    else:
        create_folders(os.path.dirname(path), destination)
        try:
            os.mkdir(os.path.join(destination, path))
        except FileExistsError:
            pass


def get_full_path(path):
    local_path = os.path.dirname(find_wit(PATH))
    if path.startswith(PATH):
        full_path, path = path, os.path.relpath(path, local_path)
    else:
        full_path = os.path.join(PATH, path)
        path = os.path.relpath(full_path, local_path)
    return path, full_path


def copy_file(path, copy_to, specific=None):
    full_path = get_full_path(path)[1]
    if os.path.isdir(full_path):
        new_path = os.path.join(copy_to, os.path.basename(path))
        try:
            os.mkdir(new_path)
        except FileExistsError:
            pass
        for item in os.listdir(full_path):
            copy_file(os.path.join(path, item), new_path, specific=specific)
    else:
        if specific is None or full_path in specific:
            shutil.copy2(full_path, copy_to)


@check_wit
def add():
    if len(sys.argv) < 3:
        raise TypeError("function 'add' must have one argument: file")
    file = sys.argv[2]
    path = os.path.dirname(file)
    path, full_path = get_full_path(path)
    wit = os.path.join(find_wit(full_path), STAGING)
    create_folders(path, wit)
    copy_to = os.path.join(wit, path)
    copy_file(file, copy_to)


def create_id():
    id_length = 40
    commit_id = []
    for _ in range(id_length):
        commit_id.append(random.choice("1234567890abcdef"))
    while commit_id in os.listdir(os.path.join(find_wit(PATH), IMAGES)):
        return create_id()
    return "".join(commit_id)


def time_format():
    zone = datetime.datetime.now(tzlocal.get_localzone()).strftime("%z")
    localtime = time.asctime(time.localtime(time.time()))
    return f"{localtime} {zone}"


def create_metadata(path, commit_id, message, parents=None):
    if parents is None:
        parents = get_head()
    else:
        parents = ", ".join(parents)
    full_message = f"parent={parents}\ndate={time_format()}\nmessage={message}"
    with open(os.path.join(path, f"{commit_id}.txt"), "w") as meta:
        meta.write(full_message)


def get_references_path():
    return os.path.join(find_wit(PATH), "references.txt")


def create_references(commit_id):
    references = get_references_path()
    with open(references, "w") as f:
            f.write(f"HEAD={commit_id}\nmaster={commit_id}\n")


def set_head(new_head):
    references = get_references_path()
    with open(references, "r") as ref:
        text = ref.readlines()
    text[0] = text[0].replace(get_head(), new_head)
    with open(references, "w") as ref:
        ref.write("".join(text))


def set_master(new_master):
    references = get_references_path()
    with open(references, "r") as file:
        text = file.readlines()
    text[1] = text[1].replace(get_master(), new_master)
    with open(references, "w") as file:
        file.write("".join(text))


def get_head():
    references = get_references_path()
    try:
        with open(references, "r") as f:
            text = f.readlines()
    except OSError:
        return
    else:
        return text[0].replace("HEAD=", "").strip()


def get_master():
    references = get_references_path()
    try:
        with open(references, "r") as f:
            text = f.readlines()
    except OSError:
        return
    return text[1].replace("master=", "").strip()


def set_branch(name, commit_id):
    references = get_references_path()
    with open(references, "r") as file:
        text = file.readlines()
    for i in range(len(text)):
        if name in text[i]:
            text[i] = f"{name}={commit_id}\n"
    with open(references, "w") as file:
        file.write("".join(text))


@check_wit
def commit():
    if len(sys.argv) < 3:
        raise TypeError("function 'commit' must have one argument: message")
    create_commit(message=sys.argv[2])


def create_commit(message, parents=None):
    wit = find_wit(PATH)
    staging_area = os.path.join(wit, STAGING)
    images_path = os.path.join(wit, IMAGES)
    commit_id = create_id()
    os.mkdir(os.path.join(images_path, commit_id))
    create_metadata(images_path, commit_id, message, parents=parents)
    if parents is not None:
        prepare_staging_to_merge(parents)
    for file in os.listdir(staging_area):
        copy_file(os.path.join(staging_area, file), os.path.join(images_path, commit_id))
    activated = get_current_branch()
    try:
        references_dict = get_references_dict()
    except FileNotFoundError:
        create_references(commit_id)
    else:
        if references_dict[activated] == get_head():
            set_branch(activated, commit_id)
        set_head(commit_id)


def prepare_staging_to_merge(parents):
    if len(parents) != 2:
        raise MergeError("If you are trying to merge please include only two branches. Else, don't include any parent")
    wit = find_wit(PATH)
    staging_area = os.path.join(wit, STAGING)
    images_path = os.path.join(wit, IMAGES)
    path1 = os.path.join(images_path, parents[0])
    path2 = os.path.join(images_path, parents[1])
    parent = get_common_parent(parents[0], parents[1])
    parent_path = os.path.join(wit, IMAGES, parent)
    for file in os.listdir(path1):
        copy_file(os.path.join(path1, file), staging_area)
    files_from_path2 = differences_list(path2, parent_path, include_folders=True) + have_no_copy(path2, parent_path, include_folders=True)
    for file in os.listdir(path2):
        copy_file(os.path.join(path2, file), staging_area, specific=files_from_path2)


def get_files_list(path, include_folders=False):
    files = [os.path.join(path, file) for file in os.listdir(path)]
    folders = list(filter(os.path.isdir, files))
    for folder in folders:
        if not include_folders:
            files.remove(folder)
        new_files = get_files_list(folder)
        files.extend(new_files)
    return files


def differences_list(path1, path2, include_folders=False):
    differences = []
    for f1 in get_files_list(path1, include_folders=include_folders):
        for f2 in get_files_list(path2, include_folders=include_folders):
            if os.path.relpath(f1, path1) == os.path.relpath(f2, path2) and not filecmp.cmp(f1, f2):
                differences.append(f1)
    return differences


def have_no_copy(path1, path2, include_folders=False):
    files1 = [os.path.relpath(file, path1) for file in get_files_list(path1, include_folders=include_folders)]
    files2 = [os.path.relpath(file, path2) for file in get_files_list(path2, include_folders=include_folders)]
    return [os.path.join(path1, file) for file in files1 if file not in files2]


def to_be_committed():
    wit = find_wit(PATH)
    head = get_head()
    last_add_path = os.path.join(wit, STAGING)
    if head is None:
        return get_files_list(last_add_path)
    last_commit_path = os.path.join(wit, IMAGES, head)
    files = differences_list(last_add_path, last_commit_path)
    files.extend(have_no_copy(last_add_path, last_commit_path))
    return files


def not_staged_for_commit():
    wit = find_wit(PATH)
    last_add_path = os.path.join(wit, STAGING)
    return differences_list(last_add_path, os.path.dirname(wit))


def untracked():
    wit = find_wit(PATH)
    files = have_no_copy(os.path.dirname(wit), os.path.join(wit, STAGING))
    return [file for file in files if WIT not in file]


@check_wit
def status():
    head = get_head()
    first = "\n".join(to_be_committed())
    second = "\n".join(not_staged_for_commit())
    third = "\n".join(untracked())
    message = f"Current id: {head}\n\nChanges to be committed:\n{first}\n\nChanges not staged for commit:\n{second}\n\nUntracked files:\n{third}"
    print(message)


def get_activated_path():
    return os.path.join(find_wit(PATH), "activated.txt")


def get_current_branch():
    with open(get_activated_path(), "r") as file:
        name = file.read()
    return name


@check_wit
def checkout():
    if len(not_staged_for_commit()) > 0 or len(to_be_committed()) > 0:
        raise CheckoutError("Can't start the function checkout. Some changes have to be committed first")
    if len(sys.argv) < 3:
        raise TypeError("function 'checkout' must have one argument: commit_id")
    do_checkout(sys.argv[2])


def do_checkout(commit_id):
    references_dict = get_references_dict()
    if commit_id in references_dict:
        with open(get_activated_path(), "w") as file:
            file.write(commit_id)
        commit_id = references_dict[commit_id]
    wit = find_wit(PATH)
    copy_from = os.path.join(wit, IMAGES, commit_id)
    for file in os.listdir(copy_from):
        copy_file(os.path.join(copy_from, file), os.path.dirname(wit))
        copy_file(os.path.join(copy_from, file), os.path.join(wit, STAGING))
    set_head(commit_id)


def get_parent(commit_id):
    with open(f"{os.path.join(find_wit(PATH), IMAGES, commit_id)}.txt", "r") as file:
        text = file.readlines()
    parent = text[0].replace("parent=", "").strip()
    if parent == "None":
        return
    if ", " in parent:
        return parent.split(", ")
    return parent


@check_wit
def graph():
    current_id = get_head()
    g = nx.DiGraph()
    if not isinstance(current_id, list):
        current_id = [current_id]
    while len(current_id) > 0:
        g.add_nodes_from(current_id)
        for one_id in current_id:
            parents = get_parent(one_id)
            if not isinstance(parents, list):
                parents = [parents]
            for parent in parents:
                if parent is not None:
                    g.add_edges_from([(one_id, parent)])
        current_id = [get_parent(one_id) for one_id in current_id]
        for one_id in current_id:
            if isinstance(one_id, list):
                current_id.extend(one_id)
                current_id.remove(one_id)
        while None in current_id:
            current_id.remove(None)
    nx.draw(g, with_labels=True)
    plt.show()


def get_references_dict():
    with open(get_references_path(), "r") as file:
        text = file.readlines()
    return dict([line.strip().split("=") for line in text[1:]])


@check_wit
def branch():
    if len(sys.argv) < 3:
        raise TypeError("function 'branch' must have one argument: name")
    name = sys.argv[2]
    if name in get_references_dict():
        raise BranchError(f"Branch named {name} already exists!")
    head = get_head()
    references = get_references_path()
    with open(references, "a") as file:
        file.write(f"{name}={head}\n")


def get_common_parent(branch1, branch2):
    parents = set(get_parents_dict(branch1))
    current_id = get_references_dict().get(branch2, branch2)
    if isinstance(current_id, list):
        current_id = set(current_id)
    else:
        current_id = {current_id}
    common_parent = current_id.intersection(parents)
    while len(common_parent) == 0:
        current_id = {get_parent(one_id) for one_id in current_id}
        for item in current_id:
            if isinstance(item, list):
                current_id.update(set(item))
                current_id.remove(item)
        common_parent = current_id.intersection(parents)
    for parent in current_id:
        if parent in parents:
            return parent


def get_parents_dict(name):
    current_id = get_references_dict().get(name, name)
    parents = {}
    if current_id is None:
        return parents
    next_id = get_parent(current_id)
    parents[current_id] = next_id
    if isinstance(next_id, list):
        for parent in next_id:
            parents.update(get_parents_dict(parent))
    else:
        parents.update(get_parents_dict(next_id))
    return parents


@check_wit
def merge():
    if len(sys.argv) < 3:
        raise TypeError("function 'merge' must have one argument: branch_name")
    name = sys.argv[2]
    activated = get_current_branch()
    references_dict = get_references_dict()
    create_commit(message=f"merge {name} into {activated}", parents=[references_dict[activated], references_dict[name]])


functions = {"init": init, "add": add, "commit": commit, "status": status, "checkout": checkout, "graph": graph, "branch": branch, "merge": merge}
functions[sys.argv[1]]()