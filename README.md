# md-card-img-extractor
从master duel里解包卡片图像，并以卡密重命名
## 执行环境和依赖
python3.12

UnityPy

ps：旧版本python和旧版本UnityPy可能无法运行
## 用法
因为我懒得写argparse，所需要自行修改变量内容进行配置

或者：

将X:\SteamLibrary\steamapps\common\Yu-Gi-Oh!  Master Duel\LocalData\1a2b3c4d\0000文件夹（根据自己情况修改） 复制到md-card-img-extractor目录下，

并且将https://dawnbrandbots.github.io/yaml-yugi/cards.json 也下载到md-card-img-extractor目录下

然后运行python md-card-img-extractor.py

## 参考项目
https://github.com/K0lb3/UnityPy

https://github.com/mikualpha/master-duel-chinese-switch
