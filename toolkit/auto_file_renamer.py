#!/usr/bin/env python3
"""Auto File Renamer - Batch rename files using patterns, OCR, and screen automation."""
import os,sys,time,json,argparse,re,shutil
from datetime import datetime
from dataclasses import dataclass,field
from typing import List,Dict
from pathlib import Path
import pyautogui
try:
    from PIL import Image;import pytesseract;HAS_OCR=True
except:HAS_OCR=False

@dataclass
class RenameRule:
    name:str;pattern:str;replacement:str;regex:bool=True;case_sensitive:bool=False
    apply_to:str="name";preview_only:bool=False

@dataclass
class RenameResult:
    original:str;renamed:str;success:bool;error:str=""

class FileRenamer:
    def __init__(self,config_path=None):
        self.config_path=config_path or os.path.expanduser("~/.file_renamer_config.json")
        self.rules:Dict[str,RenameRule]={}
        self.results:List[RenameResult]=[]
        self.load_config()
    def load_config(self):
        if os.path.exists(self.config_path):
            with open(self.config_path,"r") as f:cfg=json.load(f)
            for n,r in cfg.get("rules",{}).items():self.rules[n]=RenameRule(**r)
    def save_config(self):
        cfg={"rules":{n:{"name":r.name,"pattern":r.pattern,"replacement":r.replacement,"regex":r.regex,"case_sensitive":r.case_sensitive,"apply_to":r.apply_to} for n,r in self.rules.items()}}
        with open(self.config_path,"w") as f:json.dump(cfg,f,indent=2)
    def add_rule(self,name,pattern,replacement,regex=True):
        self.rules[name]=RenameRule(name=name,pattern=pattern,replacement=replacement,regex=regex)
        self.save_config()
    def apply_rule(self,filename,rule):
        name_part=Path(filename).stem;ext=Path(filename).suffix
        target=name_part if rule.apply_to=="name" else filename
        if rule.regex:
            flags=0 if rule.case_sensitive else re.IGNORECASE
            new_target=re.sub(rule.pattern,rule.replacement,target,flags=flags)
        else:
            if rule.case_sensitive:new_target=target.replace(rule.pattern,rule.replacement)
            else:new_target=re.sub(re.escape(rule.pattern),rule.replacement,target,flags=re.IGNORECASE)
        if rule.apply_to=="name":return new_target+ext
        return new_target
    def rename_sequential(self,directory,prefix="file",start=1,padding=3,ext_filter=None):
        files=sorted(os.listdir(directory))
        if ext_filter:files=[f for f in files if Path(f).suffix.lower() in ext_filter]
        count=start
        for fname in files:
            fpath=os.path.join(directory,fname)
            if not os.path.isfile(fpath):continue
            ext=Path(fname).suffix
            new_name=prefix+"_"+str(count).zfill(padding)+ext
            new_path=os.path.join(directory,new_name)
            try:os.rename(fpath,new_path);self.results.append(RenameResult(fname,new_name,True));count+=1
            except Exception as e:self.results.append(RenameResult(fname,new_name,False,str(e)))
        print("Renamed "+str(count-start)+" files")
    def rename_by_date(self,directory,format_str="%Y%m%d_%H%M%S",ext_filter=None):
        files=sorted(os.listdir(directory))
        if ext_filter:files=[f for f in files if Path(f).suffix.lower() in ext_filter]
        for fname in files:
            fpath=os.path.join(directory,fname)
            if not os.path.isfile(fpath):continue
            mtime=datetime.fromtimestamp(os.path.getmtime(fpath))
            ext=Path(fname).suffix
            new_name=mtime.strftime(format_str)+ext
            new_path=os.path.join(directory,new_name)
            idx=1
            while os.path.exists(new_path):new_name=mtime.strftime(format_str)+"_"+str(idx)+ext;new_path=os.path.join(directory,new_name);idx+=1
            try:os.rename(fpath,new_path);self.results.append(RenameResult(fname,new_name,True))
            except Exception as e:self.results.append(RenameResult(fname,new_name,False,str(e)))
    def rename_by_content(self,directory,ext_filter=None):
        if not HAS_OCR:print("OCR not available");return
        files=sorted(os.listdir(directory))
        if ext_filter:files=[f for f in files if Path(f).suffix.lower() in ext_filter]
        for fname in files:
            fpath=os.path.join(directory,fname)
            if not os.path.isfile(fpath):continue
            ext=Path(fname).suffix
            if ext.lower() in [".png",".jpg",".jpeg",".bmp"]:
                try:
                    img=Image.open(fpath)
                    text=pytesseract.image_to_string(img).strip()
                    words=re.findall(r"[a-zA-Z0-9]+",text)[:5]
                    if words:
                        new_name="_".join(words)[:50]+ext
                        new_name=re.sub(r"[^a-zA-Z0-9_.]","",new_name)
                        new_path=os.path.join(directory,new_name)
                        os.rename(fpath,new_path)
                        self.results.append(RenameResult(fname,new_name,True))
                except Exception as e:self.results.append(RenameResult(fname,"",False,str(e)))
    def batch_replace(self,directory,find,replace,regex=False,ext_filter=None,dry_run=False):
        rule=RenameRule(name="batch",pattern=find,replacement=replace,regex=regex)
        files=sorted(os.listdir(directory))
        if ext_filter:files=[f for f in files if Path(f).suffix.lower() in ext_filter]
        for fname in files:
            fpath=os.path.join(directory,fname)
            if not os.path.isfile(fpath):continue
            new_name=self.apply_rule(fname,rule)
            if new_name!=fname:
                if dry_run:print("  [DRY] "+fname+" -> "+new_name);self.results.append(RenameResult(fname,new_name,True))
                else:
                    try:os.rename(fpath,os.path.join(directory,new_name));self.results.append(RenameResult(fname,new_name,True))
                    except Exception as e:self.results.append(RenameResult(fname,new_name,False,str(e)))
    def undo_last(self):
        for r in reversed(self.results):
            if r.success and r.original and r.renamed:
                for d in [os.path.dirname(r.original) or ".",os.getcwd()]:
                    old=os.path.join(d,r.renamed);new=os.path.join(d,r.original)
                    if os.path.exists(old):
                        os.rename(old,new);print("Undone: "+r.renamed+" -> "+r.original);return
        print("Nothing to undo")

def main():
    parser=argparse.ArgumentParser(description="Auto File Renamer")
    parser.add_argument("--config")
    subparsers=parser.add_subparsers(dest="command")
    seq_p=subparsers.add_parser("sequential");seq_p.add_argument("directory")
    seq_p.add_argument("--prefix",default="file");seq_p.add_argument("--start",type=int,default=1)
    seq_p.add_argument("--padding",type=int,default=3);seq_p.add_argument("--ext",nargs="+")
    date_p=subparsers.add_parser("by-date");date_p.add_argument("directory")
    date_p.add_argument("--format",default="%Y%m%d_%H%M%S");date_p.add_argument("--ext",nargs="+")
    content_p=subparsers.add_parser("by-content");content_p.add_argument("directory")
    content_p.add_argument("--ext",nargs="+",default=[".png",".jpg"])
    replace_p=subparsers.add_parser("replace");replace_p.add_argument("directory")
    replace_p.add_argument("find");replace_p.add_argument("replace_with")
    replace_p.add_argument("--regex",action="store_true");replace_p.add_argument("--dry-run",action="store_true")
    replace_p.add_argument("--ext",nargs="+")
    add_r=subparsers.add_parser("add-rule");add_r.add_argument("name");add_r.add_argument("pattern");add_r.add_argument("replacement")
    subparsers.add_parser("list-rules");subparsers.add_parser("undo")
    args=parser.parse_args()
    renamer=FileRenamer(config_path=args.config)
    if args.command=="sequential":renamer.rename_sequential(args.directory,args.prefix,args.start,args.padding,args.ext)
    elif args.command=="by-date":renamer.rename_by_date(args.directory,args.format,args.ext)
    elif args.command=="by-content":renamer.rename_by_content(args.directory,args.ext)
    elif args.command=="replace":renamer.batch_replace(args.directory,args.find,args.replace_with,args.regex,args.ext,args.dry_run)
    elif args.command=="add-rule":renamer.add_rule(args.name,args.pattern,args.replacement)
    elif args.command=="list-rules":
        for n,r in renamer.rules.items():print("  "+n+": /"+r.pattern+"/ -> "+r.replacement)
    elif args.command=="undo":renamer.undo_last()
    else:parser.print_help()

if __name__=="__main__":
    main()
