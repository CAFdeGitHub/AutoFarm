import matplotlib.pyplot as plt
import matplotlib as mpl
from matplotlib.backends.backend_wxagg import FigureCanvasWxAgg as FCW
import numpy as np
from Maputil import MergedFootholds, Footholds
from time import sleep
mpl.use('WxAgg')

x_te = np.genfromtxt("plot_x.csv", delimiter=",")
y_te = np.genfromtxt("plot_y.csv", delimiter=",")
fig = plt.figure(figsize=(10,10))
ax = fig.add_subplot(111, projection='3d')
num = 50
# ax.set_xlim(-1, 1)
# ax.set_ylim(-1, 1)
# ax.set_zlim(-1, 1)
cmap = mpl.cm.tab10
for i in range(10):
    smp = x_te[i*num:(i+1)*num,:]
    # ax.view_init(elev=1., azim=2)
    ax.scatter3D(smp[:, 0], smp[:, 1], smp[:, 2], color=cmap(i), s=50, 
                 label=f"{i}")
    
    
lgd = ax.legend(bbox_to_anchor =(1.25, 0.75))

plt.show()
    

# sleep(5)



