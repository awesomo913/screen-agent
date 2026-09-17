#!/usr/bin/env python3
"""Screen Template Matcher - Find and interact with UI elements using template matching."""
import os,sys,time,json,argparse,hashlib
from datetime import datetime
from dataclasses import dataclass,field
from typing import List,Dict,Optional,Tuple
from pathlib import Path
import pyautogui
from PIL import Image
try:
    import cv2,numpy as np;HAS_CV2=True
except ImportError:HAS_CV2=False

@dataclass
class UITemplate:
    name:str;image_path:str;category:str="general";confidence:float=0.8
    click_offset:Tuple[int,int]=(0,0);description:str="";last_found:Optional[str]=None

@dataclass
class MatchResult:
    template_name:str;x:int;y:int;width:int;height:int;confidence:float;timestamp:str

class TemplateMatcher:
    def __init__(self,templates_dir=None,config_path=None):
        self.templates_dir=templates_dir or os.path.expanduser("~/screen_templates")
        self.config_path=config_path or os.path.expanduser("~/.template_matcher_config.json")
        os.makedirs(self.templates_dir,exist_ok=True)
        self.templates:Dict[str,UITemplate]={}
        self.results:List[MatchResult]=[]
        self.load_config()
    def load_config(self):
        if os.path.exists(self.config_path):
            with open(self.config_path,"r") as f:cfg=json.load(f)
            for n,t in cfg.get("templates",{}).items():
                t["click_offset"]=tuple(t.get("click_offset",[0,0]))
                self.templates[n]=UITemplate(**t)
    def save_config(self):
        cfg={"templates":{n:{"name":t.name,"image_path":t.image_path,"category":t.category,"confidence":t.confidence,"click_offset":list(t.click_offset),"description":t.description,"last_found":t.last_found} for n,t in self.templates.items()}}
        with open(self.config_path,"w") as f:json.dump(cfg,f,indent=2)
    def capture_template(self,name,region=None,category="general",description=""):
        if region:
            x,y,w,h=region
            img=pyautogui.screenshot(region=(x,y,w,h))
        else:
            print("Click and drag to select template region...")
            try:
                from pynput import mouse
                points=[]
                def on_click(mx,my,button,pressed):
                    points.append((mx,my))
                    if len(points)==2:return False
                listener=mouse.Listener(on_click=on_click)
                listener.start();listener.join()
                if len(points)==2:
                    x1=min(points[0][0],points[1][0]);y1=min(points[0][1],points[1][1])
                    w=abs(points[1][0]-points[0][0]);h=abs(points[1][1]-points[0][1])
                    img=pyautogui.screenshot(region=(x1,y1,w,h))
                else:return
            except:
                print("Cannot capture interactively");return
        path=os.path.join(self.templates_dir,name+".png")
        img.save(path)
        template=UITemplate(name=name,image_path=path,category=category,description=description)
        self.templates[name]=template;self.save_config()
        print("Template saved: "+name+" ("+str(img.size[0])+"x"+str(img.size[1])+")")
    def find_template(self,name,confidence=None,region=None):
        template=self.templates.get(name)
        if not template:print("Template not found: "+name);return None
        conf=confidence or template.confidence
        try:
            if region:
                screenshot=pyautogui.screenshot(region=region)
            else:
                screenshot=pyautogui.screenshot()
            if HAS_CV2:
                screen_arr=cv2.cvtColor(np.array(screenshot),cv2.COLOR_RGB2BGR)
                templ_img=cv2.imread(template.image_path)
                if templ_img is None:return None
                result=cv2.matchTemplate(screen_arr,templ_img,cv2.TM_CCOEFF_NORMED)
                min_val,max_val,min_loc,max_loc=cv2.minMaxLoc(result)
                if max_val>=conf:
                    h,w=templ_img.shape[:2]
                    rx=max_loc[0]+(region[0] if region else 0)
                    ry=max_loc[1]+(region[1] if region else 0)
                    template.last_found=datetime.now().isoformat();self.save_config()
                    match=MatchResult(template_name=name,x=rx,y=ry,width=w,height=h,confidence=round(max_val,3),timestamp=datetime.now().isoformat())
                    self.results.append(match)
                    return match
            else:
                loc=pyautogui.locateOnScreen(template.image_path,confidence=conf,region=region)
                if loc:
                    template.last_found=datetime.now().isoformat();self.save_config()
                    match=MatchResult(template_name=name,x=loc.left,y=loc.top,width=loc.width,height=loc.height,confidence=conf,timestamp=datetime.now().isoformat())
                    self.results.append(match);return match
        except Exception as e:print("Match error: "+str(e))
        return None
    def find_all(self,name,confidence=None):
        template=self.templates.get(name)
        if not template:return []
        conf=confidence or template.confidence
        matches=[]
        try:
            if HAS_CV2:
                screenshot=pyautogui.screenshot()
                screen_arr=cv2.cvtColor(np.array(screenshot),cv2.COLOR_RGB2BGR)
                templ_img=cv2.imread(template.image_path)
                if templ_img is None:return []
                result=cv2.matchTemplate(screen_arr,templ_img,cv2.TM_CCOEFF_NORMED)
                locations=np.where(result>=conf)
                h,w=templ_img.shape[:2]
                for pt in zip(*locations[::-1]):
                    matches.append(MatchResult(template_name=name,x=pt[0],y=pt[1],width=w,height=h,confidence=conf,timestamp=datetime.now().isoformat()))
            else:
                locs=list(pyautogui.locateAllOnScreen(template.image_path,confidence=conf))
                for loc in locs:
                    matches.append(MatchResult(template_name=name,x=loc.left,y=loc.top,width=loc.width,height=loc.height,confidence=conf,timestamp=datetime.now().isoformat()))
        except Exception as e:print("Error: "+str(e))
        return matches
    def click_template(self,name,confidence=None,double=False):
        match=self.find_template(name,confidence)
        if match:
            template=self.templates[name]
            cx=match.x+match.width//2+template.click_offset[0]
            cy=match.y+match.height//2+template.click_offset[1]
            if double:pyautogui.doubleClick(cx,cy)
            else:pyautogui.click(cx,cy)
            print("Clicked "+name+" at ("+str(cx)+","+str(cy)+")")
            return True
        print("Template not found on screen: "+name);return False
    def wait_and_click(self,name,timeout=30,confidence=None):
        start=time.time()
        while time.time()-start<timeout:
            if self.click_template(name,confidence):return True
            time.sleep(0.5)
        print("Timeout waiting for: "+name);return False
    def wait_for_template(self,name,timeout=30,confidence=None):
        start=time.time()
        while time.time()-start<timeout:
            match=self.find_template(name,confidence)
            if match:return match
            time.sleep(0.5)
        return None
    def wait_until_gone(self,name,timeout=30,confidence=None):
        start=time.time()
        while time.time()-start<timeout:
            match=self.find_template(name,confidence)
            if not match:return True
            time.sleep(0.5)
        return False

def main():
    parser=argparse.ArgumentParser(description="Screen Template Matcher")
    parser.add_argument("--templates-dir");parser.add_argument("--config")
    subparsers=parser.add_subparsers(dest="command")
    cap_p=subparsers.add_parser("capture");cap_p.add_argument("name")
    cap_p.add_argument("--region",nargs=4,type=int);cap_p.add_argument("--category",default="general")
    find_p=subparsers.add_parser("find");find_p.add_argument("name")
    find_p.add_argument("--confidence",type=float);find_p.add_argument("--all",action="store_true")
    click_p=subparsers.add_parser("click");click_p.add_argument("name")
    click_p.add_argument("--confidence",type=float);click_p.add_argument("--double",action="store_true")
    wait_p=subparsers.add_parser("wait-click");wait_p.add_argument("name")
    wait_p.add_argument("--timeout",type=float,default=30)
    subparsers.add_parser("list")
    rm_p=subparsers.add_parser("remove");rm_p.add_argument("name")
    args=parser.parse_args()
    matcher=TemplateMatcher(templates_dir=args.templates_dir,config_path=args.config)
    if args.command=="capture":
        region=tuple(args.region) if args.region else None
        matcher.capture_template(args.name,region,args.category)
    elif args.command=="find":
        if args.all:
            matches=matcher.find_all(args.name,args.confidence)
            print("Found "+str(len(matches))+" matches")
            for m in matches:print("  ("+str(m.x)+","+str(m.y)+") conf="+str(m.confidence))
        else:
            m=matcher.find_template(args.name,args.confidence)
            if m:print("Found at ("+str(m.x)+","+str(m.y)+") conf="+str(m.confidence))
            else:print("Not found")
    elif args.command=="click":matcher.click_template(args.name,args.confidence,args.double)
    elif args.command=="wait-click":matcher.wait_and_click(args.name,args.timeout)
    elif args.command=="list":
        for n,t in matcher.templates.items():print("  "+n+": "+t.category+" conf="+str(t.confidence)+" ("+t.image_path+")")
    elif args.command=="remove":
        if args.name in matcher.templates:
            p=matcher.templates[args.name].image_path
            if os.path.exists(p):os.remove(p)
            del matcher.templates[args.name];matcher.save_config()
    else:parser.print_help()

if __name__=="__main__":
    main()
