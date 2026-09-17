#!/usr/bin/env python3
"""Auto Data Entry - Automate form filling and data entry across desktop applications."""
import os,sys,time,json,argparse,csv
from datetime import datetime
from dataclasses import dataclass,field
from typing import List,Dict,Optional,Tuple
import pyautogui,pyperclip
try:
    import pytesseract;HAS_TESSERACT=True
except ImportError:HAS_TESSERACT=False
try:
    from pynput import keyboard
except ImportError:keyboard=None

@dataclass
class FormField:
    name:str;field_type:str="text";x:int=0;y:int=0;tab_order:int=0
    options:List[str]=field(default_factory=list);required:bool=False

@dataclass
class FormTemplate:
    name:str;fields:List[FormField]=field(default_factory=list);app_title:str=""
    submit_method:str="enter";delay_between:float=0.3

@dataclass
class DataRecord:
    values:Dict[str,str]=field(default_factory=dict);status:str="pending"

class FormDetector:
    def detect_fields_ocr(self,region=None):
        if not HAS_TESSERACT:return []
        img=pyautogui.screenshot(region=region) if region else pyautogui.screenshot()
        data=pytesseract.image_to_data(img,output_type=pytesseract.Output.DICT)
        fields=[]
        for i,text in enumerate(data["text"]):
            t=text.strip()
            if t and (":" in t or t.endswith("*") or t.lower() in ["name","email","phone","address","city","state","zip","date","company"]):
                fields.append(FormField(name=t.rstrip(":*").strip(),x=data["left"][i]+data["width"][i]+10,y=data["top"][i]+data["height"][i]//2,tab_order=len(fields)))
        return fields
    def detect_by_tab(self,num_fields=10):
        fields=[]
        for i in range(num_fields):
            pyautogui.press("tab");time.sleep(0.2)
            x,y=pyautogui.position()
            fields.append(FormField(name="field_"+str(i+1),x=x,y=y,tab_order=i))
        return fields

class DataEntryAutomator:
    def __init__(self,config_path=None):
        self.config_path=config_path or os.path.expanduser("~/.data_entry_config.json")
        self.templates:Dict[str,FormTemplate]={}
        self.detector=FormDetector()
        self.load_config()
    def load_config(self):
        if os.path.exists(self.config_path):
            with open(self.config_path,"r") as f:cfg=json.load(f)
            for name,tdata in cfg.get("templates",{}).items():
                fields=[FormField(**fd) for fd in tdata.get("fields",[])]
                self.templates[name]=FormTemplate(name=name,fields=fields,app_title=tdata.get("app_title",""),submit_method=tdata.get("submit_method","enter"),delay_between=tdata.get("delay_between",0.3))
    def save_config(self):
        cfg={"templates":{}}
        for n,t in self.templates.items():
            cfg["templates"][n]={"fields":[{"name":f.name,"field_type":f.field_type,"x":f.x,"y":f.y,"tab_order":f.tab_order,"options":f.options,"required":f.required} for f in t.fields],"app_title":t.app_title,"submit_method":t.submit_method,"delay_between":t.delay_between}
        with open(self.config_path,"w") as f:json.dump(cfg,f,indent=2)
    def create_template(self,name,num_fields=None,detect_ocr=False):
        if detect_ocr:
            fields=self.detector.detect_fields_ocr()
        elif num_fields:
            fields=self.detector.detect_by_tab(num_fields)
        else:
            fields=[]
        template=FormTemplate(name=name,fields=fields)
        self.templates[name]=template;self.save_config()
        print("Template '"+name+"': "+str(len(fields))+" fields")
        return template
    def fill_field(self,fld,value):
        if fld.x and fld.y:
            pyautogui.click(fld.x,fld.y);time.sleep(0.1)
        if fld.field_type=="text":
            pyautogui.hotkey("ctrl","a");pyautogui.typewrite(str(value),interval=0.01)
        elif fld.field_type=="dropdown":
            pyautogui.click(fld.x,fld.y);time.sleep(0.3)
            pyautogui.typewrite(str(value),interval=0.02);pyautogui.press("enter")
        elif fld.field_type=="checkbox":
            if str(value).lower() in ["true","yes","1","on"]:
                pyautogui.click(fld.x,fld.y)
        elif fld.field_type=="radio":
            pyautogui.click(fld.x,fld.y)
        elif fld.field_type=="date":
            pyautogui.hotkey("ctrl","a");pyautogui.typewrite(str(value),interval=0.02)
        elif fld.field_type=="textarea":
            pyperclip.copy(str(value));pyautogui.hotkey("ctrl","v")
    def fill_form(self,template_name,data,submit=False):
        template=self.templates.get(template_name)
        if not template:print("Template not found");return
        sorted_fields=sorted(template.fields,key=lambda f:f.tab_order)
        for fld in sorted_fields:
            if fld.name in data:
                self.fill_field(fld,data[fld.name])
                time.sleep(template.delay_between)
        if submit:
            if template.submit_method=="enter":pyautogui.press("enter")
            elif template.submit_method=="tab_enter":pyautogui.press("tab");time.sleep(0.2);pyautogui.press("enter")
            elif template.submit_method=="click":pass
            time.sleep(1)
        print("Form filled with "+str(len(data))+" values")
    def batch_fill(self,template_name,records,submit_each=True,delay_between_records=1.0):
        print("Batch filling "+str(len(records))+" records...")
        for i,record in enumerate(records):
            print("  Record "+str(i+1)+"/"+str(len(records)))
            self.fill_form(template_name,record,submit=submit_each)
            time.sleep(delay_between_records)
        print("Batch complete")
    def load_csv_data(self,csv_path):
        records=[]
        with open(csv_path,"r",encoding="utf-8") as f:
            reader=csv.DictReader(f)
            for row in reader:records.append(dict(row))
        return records

def main():
    parser=argparse.ArgumentParser(description="Auto Data Entry")
    parser.add_argument("--config")
    subparsers=parser.add_subparsers(dest="command")
    create_p=subparsers.add_parser("create-template");create_p.add_argument("name")
    create_p.add_argument("--fields",type=int);create_p.add_argument("--detect-ocr",action="store_true")
    fill_p=subparsers.add_parser("fill");fill_p.add_argument("template")
    fill_p.add_argument("--data",required=True,help="JSON data");fill_p.add_argument("--submit",action="store_true")
    batch_p=subparsers.add_parser("batch");batch_p.add_argument("template")
    batch_p.add_argument("csv_file");batch_p.add_argument("--submit",action="store_true")
    batch_p.add_argument("--delay",type=float,default=1.0)
    subparsers.add_parser("list-templates")
    args=parser.parse_args()
    automator=DataEntryAutomator(config_path=args.config)
    if args.command=="create-template":automator.create_template(args.name,args.fields,args.detect_ocr)
    elif args.command=="fill":
        data=json.loads(args.data);automator.fill_form(args.template,data,args.submit)
    elif args.command=="batch":
        records=automator.load_csv_data(args.csv_file);automator.batch_fill(args.template,records,args.submit,args.delay)
    elif args.command=="list-templates":
        for n,t in automator.templates.items():print("  "+n+": "+str(len(t.fields))+" fields")
    else:parser.print_help()

if __name__=="__main__":
    main()
