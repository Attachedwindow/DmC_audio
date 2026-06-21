下载QuickBMS
https://github.com/LittleBigBug/QuickBMS/releases



打开cmd，按照提示编辑并运行以下命令行内容

【QuickBMS下载目录】\quickbms.exe 【文件地址】\DmC_APK_to_BNK.bms 【文件地址+.apk格式的文件名】 C:\Users\Admin\Desktop\Extracted_BNK【此条无需更改，回车后键入Y回车就会在桌面生成文件夹】
【QuickBMS下载目录】\quickbms.exe 【文件地址】\DmC_BNK_to_WEM.bms 【文件地址】\Extracted_BNK C:\Users\Admin\Desktop\Extracted_WEM

.apk（AudioPackage）文件在D:\steam\steamapps\common\DmC Devil May Cry\DevilGame\CookedPCConsole
直接打开游戏安装目录从左上角搜索也可以



下载Python（没有版本要求）：

https://www.python.org/downloads/
在installer中务必勾选最下面的选项；卸载python也要用installer卸载。

Wwiser发布页（此资源内有，无需下载）
https://github.com/bnnm/wwiser
打开Wwiser_Python文件夹，双击运行wwiser.pyz

在弹出的界面里点击Load dirs，指向做完上述两个指令后生成的两个文件夹所存在的目录
滚动完毕后点击View banks即可查看

ctrl+s选择mhtml模式能保存为可以发给别人的格式，hmtl只方便自己查看（因为要连带其他文件一起发送）



编辑工具Wwiseutil发布页：
https://github.com/hpxro7/wwiseutil/releases/


其他：
点击Dump banks保存为txt文件
我们无法用Wwiser Authoring Tool进行可视化修改，以上得到的文件都是经过编译打包的。
理论上可以用WWAT编译出wem文件再到Wwiseutil里替换，但需要注意原始音频采样率和声道，以及偏移量等等。