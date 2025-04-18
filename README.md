# TCE-PIP

### Origin story
If you found this, you're probably familiar with both Tiny Core Linux and Python.  
Quite likely you've already installed some packages through Pip (or another package manager) and noticed the packages end up in user space resulting in a large `mydata.tgz` resulting in slow backups and long boot times.  
Maybe you even tried to manually package up the `site-packages` directory into a `.tcz` file, although this becomes tedious quickly.  
This is when I decided we all need a wrapper script to be able to install Pip packages as seperate tcz packages. To declutter the user space, speed up boot times and maintain Python package versions easier.  
And thus `TCE-PIP` was born&hellip;

### Installation
1. Make sure you have Python installed
2. Install dependencies: `tce-load -wi squashfs-tools`
3. Run `wget -P /etc/sysconfig/tcedir/optional https://github.com/BillyNate/tce-pip/releases/latest/download/tce-pip.tcz && tce-load -i tce-pip.tcz && echo "tce-pip.tcz" >> /etc/sysconfig/tcedir/onboot.lst`
4. Run `tce-pip install` once to install pip and other necessary packages

### Usage
To install a Pip package, run `tce-pip install packagename`.

### What does is actually do?
`tce-pip` downloads the pip package including dependencies using a simple `pip download` into a temporary directory  
All pip packages are installed into their own temporary directory and needed metadata is extracted  
The pip packages are packaged up into seperate tc packages with their metadata  
The system's tcemirror is set to localhost and an http server is started  
The requested package gets installed with its dependencies  
The tcemirror is restored to its old setting  

### Tips
Using Piwheel as a source for the Python packages will significantly speed up installation.
1. Create directory: `mkdir ~/.pip`
2. Create file `~/.pip/pip.conf` and add:
   ```
   [global]
   extra-index-url=https://www.piwheels.org/simple
   ```
3. If your Python version doesn't match [piwheel's support](//www.piwheels.org#support), add these lines to use wheels for an older Python version:
   ```
   python-version=311
   only-binary=:all:
   target=/home/tc/.local/lib/python3.13/site-packages
   ```
   Make sure path in `target=` matches your Python version. The target path is now identical to a `--user` install.
4. Save changes: `backup`
