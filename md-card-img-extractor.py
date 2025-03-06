import os
import UnityPy
from multiprocessing import pool
from functools import partial
import zlib
import struct
import json
import shutil


def unpack_all_assets(source_folder : str, destination_folder : str,thread:int):
    flist=[]
    for root, dirs, files in os.walk(source_folder):
        for file_name in files:
            file_path = os.path.join(root, file_name)
            flist.append(file_path)

    with pool.Pool(thread) as pl:
        pl.map(partial(unpack_single_file,destination_folder=destination_folder),flist)

def unpack_single_file(file_path,destination_folder):
    env = UnityPy.load(file_path)
    for path,obj in env.container.items():
        try :
            if obj.type.name in ["Texture2D", "Sprite","TextAsset"]:
                data = obj.read()
                dest = os.path.join(destination_folder, *path.split("/"))
                os.makedirs(os.path.dirname(dest), exist_ok = True)
                dest, ext = os.path.splitext(dest)
                dest = dest + ".png"
                data.image.save(dest)
        except:
            pass

        try:
            if obj.type.name=="TextAsset":
                data = obj.read()
                dest = os.path.join(destination_folder, *path.split("/"))
                os.makedirs(os.path.dirname(dest), exist_ok = True)
                with open(dest, "wb") as file:
                    file.write(bytes(data.m_Script.encode("utf-8", "surrogateescape")))
        except:
            pass

#from https://github.com/mikualpha/master-duel-chinese-switch
def crack_key(b: bytes) -> int:
    def helper(b: bytes, m_iCryptoKey):
        data = bytearray(b)
        for i in range(len(data)):
            v = i + m_iCryptoKey + 0x23D
            v *= m_iCryptoKey
            v ^= i % 7
            data[i] ^= v & 0xFF
        zlib.decompress(data)

    for i in range(0xFF):
        m_iCryptoKey = i
        try:
            helper(b, m_iCryptoKey)
            return m_iCryptoKey
        except Exception as e:
            pass

    return -1

#modify from https://github.com/mikualpha/master-duel-chinese-switch
def decrypt(path:str, m_iCryptoKey: int) -> str:
    if os.path.exists(path):
        with open(path,"rb") as file:
            data=bytearray(file.read())

        for i in range(len(data)):
            v = i + m_iCryptoKey + 0x23D
            v *= m_iCryptoKey
            v ^= i % 7
            data[i] ^= v & 0xFF
        
        result=zlib.decompress(data)
    else:
        result=""

    return result

#from https://github.com/mikualpha/master-duel-chinese-switch
def cidProcess(b: bytes, skip_num: int):
    start_pos = skip_num * 8
    cid_list = []
    while True:
        if start_pos + 2 >= len(b):
            break
        data = b[start_pos:start_pos + 2]
        if not data:
            break
        value = struct.unpack("<H", data)[0]
        cid_list.append(value)
        # print(value)

        start_pos += 8
    return cid_list

#from https://github.com/mikualpha/master-duel-chinese-switch
def progressiveProcess(
    b: bytes, b_indx: bytes, start: int, should_skip: bool = True
) -> list[str]:

    # 读取二进制indx
    hex_str_list = ("{:02X}".format(int(c)) for c in b_indx)  # 定义变量接受文件内容
    dec_list = [int(s, 16) for s in hex_str_list]  # 将十六进制转换为十进制

    # 拿到desc的indx
    _indx: list[list[int]] = []
    for i in range(start, len(dec_list), 8 if should_skip else 4):
        tmp: list[int] = []
        for j in range(4):
            tmp.append(dec_list[i + j])
        _indx.append(tmp)

    def fourToOne(x: list[int]) -> int:
        res = 0
        for i in range(3, -1, -1):
            res *= 16 * 16
            res += x[i]
        return res

    indx = [fourToOne(i) for i in _indx]
    indx = indx[1:]
    """
    将解密后的CARD文件转换为JSON文件
    """

    def solve(data: bytes, desc_indx: list[int]) -> list[str]:
        res: list[str] = []
        for i in range(len(desc_indx) - 1):
            s = data[desc_indx[i] : desc_indx[i + 1]]
            s = s.decode("UTF-8")
            while len(s) > 0 and s[-1] == "\u0000":
                s = s[:-1]
            res.append(s)
        return res

    return solve(b, indx)

def getCardInfo(outdir:str,lang:str):
    textPath=outdir+r"\assets\resourcesassetbundle\card\data"
    textPath=os.path.join(textPath,os.listdir(textPath)[0],lang)

    with open(os.path.join(textPath,"card_same.bytes"),"rb") as file:
        data=file.read()
    m_iCryptoKey=crack_key(data)

    card_data={}
    for i in ["card_desc","card_indx","card_name","card_pidx","card_prop","card_same"]:
        card_data[i]=decrypt(os.path.join(textPath,f"{i}.bytes"),m_iCryptoKey)
    name=progressiveProcess(card_data["card_name"], card_data["card_indx"], 0)
    index=cidProcess(card_data["card_prop"], 1)
    return name,index

#nead https://dawnbrandbots.github.io/yaml-yugi/cards.json
def loadDB(dbpath:str):
    with open(dbpath,'r') as f:
        data=json.load(f)

    #只提取必要内容
    db={}
    for d in data:
        if (kid:=d.get('konami_id')) is not None:
            db[kid]=d.get('password')
    return db

def copyCardPic(pdir:str,outdir:str,db:dict,name:list,index:list):

    if not os.path.exists(pdir):
        os.mkdir(pdir)

    if not os.path.exists(p:=os.path.join(pdir,"ocg")):
        os.mkdir(p)

    if not os.path.exists(p:=os.path.join(pdir,"tcg")):
        os.mkdir(p)

    nfList=[]#卡图未发现
    npwList=[]#卡密未发现
    cpicPath=outdir+r"\assets\resources\card\images\illust"
    cpicPath2=outdir+r"\assets\resourcesassetbundle\card\images\illust\tcg" #个别卡在这个目录

    for i in range(len(index)):
        if (pw:=db.get(ind:=index[i])) is not None:
            subp=f"{ind:05d}"[:2]
            nf=True
            #ocg
            if os.path.exists(pPath:=os.path.join(cpicPath,"common",subp,f"{ind}.png")):
                if not os.path.exists(oPath:=os.path.join(pdir,"ocg",f"{pw}.png")):
                    shutil.copy(pPath,oPath)
                nf=False
            #tcg
            if os.path.exists(pPath:=os.path.join(cpicPath,"tcg",subp,f"{ind}.png")):
                if not os.path.exists(oPath:=os.path.join(pdir,"tcg",f"{pw}.png")):
                    shutil.copy(pPath,oPath)
                nf=False
            #tcg part2
            if os.path.exists(pPath:=os.path.join(cpicPath2,f"{ind}.png")):
                if not os.path.exists(oPath:=os.path.join(pdir,"tcg",f"{pw}.png")):
                    shutil.copy(pPath,oPath)
                nf=False
            if nf:
                nfList.append(i)

            
        else:
            subp=f"{ind:05d}"[:2]
            nf = not (os.path.exists(os.path.join(cpicPath,"common",subp,f"{ind}.png")) 
                or os.path.exists(os.path.join(cpicPath,"tcg",subp,f"{ind}.png"))
                or os.path.exists(os.path.join(cpicPath2,f"{ind}.png")))
            if nf:
                nfList.append(i)
            else:
                npwList.append(i)

    with open("pic-not-found.txt","w",encoding="utf-8") as file:
        file.write("index\tmap\tname\n")

        for i in nfList:
            file.write(f"{index[i]}\t\t{name[i]}\n")
        
    #with open("pw-not-found.txt","w",encoding="utf-8") as file:
    #    file.write("index\tmap\tname\n")

    #    for i in npwList:
    #        file.write(f"{index[i]}\t\t{name[i]}\n")

    return nfList,npwList

def applyExMap(outdir:str,expath:str,npwList:list,index:list):
    cpicPath=outdir+r"\assets\resources\card\images\illust"
    cpicPath2=outdir+r"\assets\resourcesassetbundle\card\images\illust\tcg" 

    
    with open (expath,encoding="utf-8") as file:
        exmapRaw=file.read().split("\n")
    
    exmap={}
    for line in exmapRaw[1:]:
        if (len(datas:=line.split("\t"))>=2):
            exmap[int(datas[0])]=[datas[1]]
        if (len(datas)>3 and datas[3].lower()=="force"):
            exmap[int(datas[0])].append(True)

    tmpSet=set(exmap.keys())
    newNpwList=[]
    for i in npwList:
        tmpSet.discard(ind:=index[i])
        if (m:=exmap.get(ind)) is None:
            newNpwList.append(i)
            continue
        if len(m)==1:
            m.append(False)

        force=m[1]
        for p in m[0].split("|"):
            pw=int(p)
            if pw<0:
                continue
            subp=f"{ind:05d}"[:2]
            #ocg
            if os.path.exists(pPath:=os.path.join(cpicPath,"common",subp,f"{ind}.png")):
                if (not os.path.exists(oPath:=os.path.join(pdir,"ocg",f"{pw}.png"))) or force :
                    shutil.copy(pPath,oPath)
            #tcg
            if os.path.exists(pPath:=os.path.join(cpicPath,"tcg",subp,f"{ind}.png")):
                if (not os.path.exists(oPath:=os.path.join(pdir,"tcg",f"{pw}.png"))) or force:
                    shutil.copy(pPath,oPath)
            #tcg part2
            if os.path.exists(pPath:=os.path.join(cpicPath2,f"{ind}.png")):
                if (not os.path.exists(oPath:=os.path.join(pdir,"tcg",f"{pw}.png"))) or force:
                    shutil.copy(pPath,oPath)

    for ind in tmpSet:
        m=exmap.get(ind)

        if len(m)==1:
            m.append(False)

        force=m[1]
        for p in m[0].split("|"):
            pw=int(p)
            if pw<0:
                continue
            subp=f"{ind:05d}"[:2]
            #ocg
            if os.path.exists(pPath:=os.path.join(cpicPath,"common",subp,f"{ind}.png")):
                if (not os.path.exists(oPath:=os.path.join(pdir,"ocg",f"{pw}.png"))) or force :
                    shutil.copy(pPath,oPath)
            #tcg
            if os.path.exists(pPath:=os.path.join(cpicPath,"tcg",subp,f"{ind}.png")):
                if (not os.path.exists(oPath:=os.path.join(pdir,"tcg",f"{pw}.png"))) or force:
                    shutil.copy(pPath,oPath)
            #tcg part2
            if os.path.exists(pPath:=os.path.join(cpicPath2,f"{ind}.png")):
                if (not os.path.exists(oPath:=os.path.join(pdir,"tcg",f"{pw}.png"))) or force:
                    shutil.copy(pPath,oPath)

    with open("pw-not-found.txt","w",encoding="utf-8") as file:
        file.write("index\tmap\tname\n")

        for i in newNpwList:
            file.write(f"{index[i]}\t\t{name[i]}\n")

    return newNpwList


if __name__ == "__main__":
    srcdir=r"S:\tmp\0000" # master duel game resource path
    # e.g.： X:\SteamLibrary\steamapps\common\Yu-Gi-Oh!  Master Duel\LocalData\1a2b3c4d\0000
    outdir=r"output" #unpack output dir
    pdir=r"pics"  # final card images output dir
    dbpath="cards.json" #cards.json path (https://dawnbrandbots.github.io/yaml-yugi/cards.json)
    thread=8 #thread for unpacking
    skipUnpack=False #skip unpack（avoid duplicate unpacking）
    lang="zh-cn" # language of master duel，only test under Chinese Simplified
    extraMap="exmap.txt" #extra map list，for card password not found by Konami ID

    if not os.path.exists(outdir):
        os.mkdir(outdir)

    if not skipUnpack:
        unpack_all_assets(srcdir,outdir,thread)

    name,index=getCardInfo(outdir,lang)

    nfList,npwList=copyCardPic(pdir,outdir,loadDB(dbpath),name,index)
    npwList=applyExMap(outdir,extraMap,npwList,index)



    
