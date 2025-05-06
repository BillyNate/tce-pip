import os
import platform
import sys
from contextlib import nullcontext, redirect_stdout, redirect_stderr
from glob import glob
from hashlib import file_digest, md5
from importlib.util import find_spec
from io import StringIO
from logging import getLogger
from math import log
from re import match, split, sub
from shutil import rmtree
from site import getsitepackages
from subprocess import PIPE, Popen
from threading import Thread
from time import sleep

_LOGGER = getLogger(__name__)

# Declare variables for use in eval():
platform_python_implementation = platform.python_implementation()
platform_machine = platform.machine()
platform_system = platform.system()
python_version = platform.python_version()
sys_platform = sys.platform
os_name = os.name
extra = ""

# Prepare env for later use
env = os.environ.copy()

def sanitize_packagename(packagename):
  return sub(r"[-_.]+", "-", packagename).lower()

def package_version_check(packagename):
  splitted_packagename = split(r"(\=\=\=|~\=|\=\=|<\=|>\=|!\=|<|>)", packagename)
  if len(splitted_packagename) > 1:
    return { 'name': splitted_packagename[0], 'version': splitted_packagename[2], 'delimiter': splitted_packagename[1] }
  return { 'name': packagename }

def req_filter(req):
  from packaging.version import Version

  if ";" in req:
    delimit = req.split(";", 1)[1]
    if "python_version" in delimit:
      delimit = delimit.replace("python_version", "Version(python_version)")
      delimit = sub(r"(['\"][\d\.]+['\"])", "Version(\\1)", delimit, 0)
    if not eval(delimit.strip()):
      return False
  return True

def req_naming(req):
  if ";" in req:
    req = req.split(";", 1)[0].strip()
  req = req.strip().lower()
  req = match(r"[A-Za-z0-9+_-]+", req).group(0)
  req = sanitize_packagename(req)
  return "tce-pip-" + req  + ".tcz"

def pretty_size(n,pow=0,b=1024,u='B',pre=['']+[p for p in'KMGTPEZY']):
  pow,n=min(int(log(max(n*b**pow,1),b)),len(pre)-1),n*b**pow
  return "%%.%if %%s%%s"%abs(pow%(-pow-1))%(n/b**float(pow),pre[pow],u)

def piprun(silent, args):
  from pip import _internal as pipinternal

  with redirect_stdout(StringIO()) as stdout_string, redirect_stderr(StringIO()) as stderr_string:
    temp_stdout_string = ""
    coll_stdout_string = ""
    temp_stderr_string = ""
    coll_stderr_string = ""
    thread = Thread(target=pipinternal.main, args=(args,))
    thread.start()
    while thread.is_alive():
      if silent:
        sleep(1)
        #sys.__stdout__.write(".")
        #sys.__stdout__.flush()
      else:
        sleep(.1)
        temp_stdout_string = stdout_string.getvalue()
        temp_stderr_string = stderr_string.getvalue()
        if len(temp_stdout_string) > 0:
          stdout_string.truncate(0)
          stdout_string.seek(0)
          #sys.__stdout__.write("[[[\n")
          sys.__stdout__.write(temp_stdout_string)
          #sys.__stdout__.write("]]]\n")
          sys.__stdout__.flush()
          coll_stdout_string += temp_stdout_string
          temp_stdout_string = ""
        if len(temp_stderr_string) > 0:
          stderr_string.truncate(0)
          stderr_string.seek(0)
          if temp_stderr_string.startswith("WARNING: pip is being invoked by an old script wrapper"):
            #sys.__stderr__.write("((_____))")
            sys.__stderr__.write("")
          else:
            #sys.__stderr__.write("<<\n")
            sys.__stderr__.write(temp_stderr_string)
            #sys.__stderr__.write(">>\n")
          sys.__stderr__.flush()
          coll_stderr_string += temp_stderr_string
          temp_stderr_string = ""
  if silent:
    #sys.__stdout__.write("\n")
    sys.__stdout__.write("")
  return coll_stdout_string, coll_stderr_string

def create_package(fromdir, tofile):
  with Popen(["mksquashfs", fromdir, tofile, "-noappend", "-quiet", "-progress"], stdin=PIPE, stderr=PIPE, env=env, close_fds=False) as process:
    _, stderr = process.communicate()
    if process.returncode != 0:
      _LOGGER.error("Unable to create extension")
      exit()

def install_package(packagefile, download=False):
  arguments = "-i" + ("w" if download else "")
  with Popen(["tce-load", arguments, packagefile], stdin=PIPE, stdout=PIPE, stderr=PIPE, env=env, close_fds=False) as process:
    _, stderr = process.communicate()
    if process.returncode != 0:
      _LOGGER.error("Unable to install extension")
      exit()

def prepare_package(deppkg, repodir, installdir, infocontent):  
  from pkginfo import get_metadata

  env = os.environ.copy()
  metadata = get_metadata(deppkg)
  pkgname = sanitize_packagename(metadata.name)
  tczfile = repodir + "/tce-pip-" + pkgname + ".tcz"

  # Don't touch pip:
  if pkgname == "pip":
    return

  # Create .dep file:
  #print(metadata.requires_dist)
  requirements = [req_naming(req) for req in metadata.requires_dist if req_filter(req)]
  if "tce-pip-pip.tcz" in requirements:
    requirements.remove("tce-pip-pip.tcz")
  #print(requirements)
  if requirements:
    depsfile = open(repodir + "/tce-pip-" + sanitize_packagename(metadata.name) + ".tcz.dep", "a+")
    depsfile.write("\n".join(requirements))
    depsfile.close()

  # Install pip package in our own install dir:
  out, err = piprun(False, ["install", "--no-compile", "--no-deps", "--ignore-installed", "--target=" + installdir + getsitepackages()[0], deppkg])
  # Remove no longer needed wheel file:
  os.remove(deppkg)

  # Create package from installdir:
  print("Packaging " + pkgname + " into Tiny Core package...")
  create_package(installdir, tczfile)

  pkgsize = pretty_size(os.stat(tczfile).st_size)

  # Create md5 hash file:
  with open(tczfile, "rb") as filetohash:
    with open(tczfile + ".md5.txt", "w") as md5file:
      md5file.write(file_digest(filetohash, md5).hexdigest() + " tce-pip-" + pkgname + ".tcz")

  # Create list file:
  with open(tczfile + ".list", "w") as listfile:
    listfile.write("\n".join([os.path.relpath(filename, installdir + "/") for filename in glob(installdir + "/" + '**/*', recursive=True) if os.path.isfile(filename)]))

  # Create info file:
  with open(tczfile + ".info", "w") as infofile:
    infocontent = infocontent.replace("title", "tce-pip-" + pkgname)
    infocontent = infocontent.replace("description", metadata.summary or "N/A")
    infocontent = infocontent.replace("version", metadata.version or "0")
    infocontent = infocontent.replace("author", metadata.author or "Unknown")
    infocontent = infocontent.replace("site", metadata.home_page or "N/A")
    infocontent = infocontent.replace("policy", metadata.license or "Unknown")
    infocontent = infocontent.replace("size", pkgsize)
    infofile.write(infocontent);

  rmtree(installdir)
