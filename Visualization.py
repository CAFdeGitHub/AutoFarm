import matplotlib.pyplot as plt
import matplotlib as mpl
from matplotlib.backends.backend_wxagg import FigureCanvasWxAgg as FCW
import numpy as np
from Maputil import MergedFootholds, Footholds, y_shift_by_x, x_shift_by_forward_jump, JUMP_ROPE_AWAY_DISTNACE
from time import sleep
from threading import Thread, Lock
mpl.use('WxAgg')

class MapVisualization:

    def __init__(self, flist, ladderlist, max_mob_count, refresh_time=1):
        self.flist = flist
        self.ladderlist = ladderlist
        self.max_mob_count = max_mob_count
        self.initialize_map()
        self.lock = Lock()
        self.character_coor = None
        self.all_mob_coor = None
        self.refresh_time = refresh_time

    def start(self):
        self.stopped = False
        t = Thread(target=self.run)
        t.start()

    def update_mapinfo(self, mapinfo):
        self.lock.acquire()
        self.all_mob_coor = mapinfo.all_mob_coor
        self.character_coor = mapinfo.character_coor
        self.lock.release()


    def stop(self):
        self.stopped = True


    def run(self):
        while not self.stopped:
            if self.character_coor is not None:
                self.plot_map()
                sleep(self.refresh_time)

    def initialize_map(self):
        fig_size=(10, 5)
        fig = plt.figure(figsize=fig_size)
        ax = plt.gca()
        ax.invert_yaxis()
        cmap = mpl.cm.tab20c
        # cmap = mpl.colors.ListedColormap(["red", "green"])
        i = 0
        for n in self.flist:
            if isinstance(n, MergedFootholds):
                ax.plot(n.get_plot_point()[0], n.get_plot_point()[1], color=cmap(i))
                # ax.text(sum(n.get_plot_point()[0])/len(n.get_plot_point()[0]), 
                         # sum(n.get_plot_point()[1])/len(n.get_plot_point()[0]), f"{i}", horizontalalignment="center")
            elif isinstance(n, Footholds):
                ax.plot(n.get_plot_point()[0], n.get_plot_point()[1],  color=cmap(i))
                # ax.text(sum(n.get_plot_point()[0])/2, 
                         # sum(n.get_plot_point()[1])/2, f"{i}", horizontalalignment="center")
            i += 1
        for ladder in self.ladderlist:
        #         fig.add_artist(lines.Line2D([x1, y1], [x2, y2]))
                ax.plot(ladder.get_plot_point()[0], ladder.get_plot_point()[1], color="tan")

        self.character_rect = mpl.patches.Rectangle((0, 0), 20, -10, linewidth=1, edgecolor='green', facecolor='green', animated=True)
        ax.add_patch(self.character_rect)
        self.mob_rec_list = [mpl.patches.Rectangle((0, 0), 20, -10, linewidth=1, edgecolor='red', facecolor='red', animated=True) for i in range(self.max_mob_count)]
        for mob_rect in self.mob_rec_list:
            ax.add_patch(mob_rect)
        # x = np.linspace(0, 2 * np.pi, 100)
        # (ln,) = ax.plot(x, np.sin(x), animated=True)
        plt.show(block=False)
        # plt.pause(1)
        self.bg = fig.canvas.copy_from_bbox(fig.bbox)
        fig.canvas.blit(fig.bbox)
        self.fig = fig
        self.ax = ax

    def plot_map(self):
        # set character_coor, mob_coor
        self.lock.acquire() # prevent coor to be modified
        self.character_rect.set_xy(self.character_coor)
        mob_count = len(self.all_mob_coor)
        for i in range(mob_count):
            self.mob_rec_list[i].set_xy(all_mob_coor[i])
        self.lock.release() 
        # render it by blitting
        self.fig.canvas.restore_region(self.bg)
        self.ax.draw_artist(self.character_rect)
        for i in range(mob_count):
            self.ax.draw_artist(self.mob_rec_list[i])
        self.fig.canvas.blit(self.fig.bbox)
        self.fig.canvas.flush_events()


    def plot_lower_jump(self, lower_jump_edge, show_index=False):
        cmap = mpl.cm.tab20c
        self.fig.canvas.restore_region(self.bg)
        i = 0
        for lower_jump in lower_jump_edge:
            for j in lower_jump.jump_seg_list:
                self.ax.draw_artist(self.ax.plot((j[0], j[0]), (lower_jump.start_area.lower_y, lower_jump.dest_area.lower_y), color=cmap(i), marker='o')[0])
                self.ax.draw_artist(self.ax.plot((j[1], j[1]), (lower_jump.start_area.lower_y, lower_jump.dest_area.lower_y), color=cmap(i), marker='o')[0])
                if show_index:
                    self.ax.draw_artist(self.ax.text(j[0], (lower_jump.start_area.lower_y + lower_jump.dest_area.lower_y)/2, f"{i}", horizontalalignment="center"))
                    self.ax.draw_artist(self.ax.text(j[1], (lower_jump.start_area.lower_y + lower_jump.dest_area.lower_y)/2, f"{i}", verticalalignment="center"))
            i += 1
        self.fig.canvas.blit(self.fig.bbox)
        self.fig.canvas.flush_events()
        sleep(10)




    def plot_falling(self, falling_edge, show_index=False):
        cmap = mpl.cm.tab20c
        self.fig.canvas.restore_region(self.bg)
        i = 0
        for falling in falling_edge:
            if falling.falling_dir == "left":
                self.ax.draw_artist(self.ax.arrow(falling.start_area.left_x, falling.start_area.left_y, 
                          0, falling.dest_area.y_at_location_x(falling.start_area.left_x) - falling.start_area.left_y, 
                          length_includes_head=True, head_width=10))
            if falling.falling_dir == "right":
                self.ax.draw_artist(self.ax.arrow(falling.start_area.right_x, falling.start_area.right_y, 
                          0, falling.dest_area.y_at_location_x(falling.start_area.right_x) - falling.start_area.right_y, 
                          length_includes_head=True, head_width=10))
            i += 1
        self.fig.canvas.blit(self.fig.bbox)
        self.fig.canvas.flush_events()
        sleep(10)


    def plot_forward_jump(self, forward_jump_edge, show_index=False):
        cmap = mpl.cm.tab20c
        self.fig.canvas.restore_region(self.bg)
        i = 0
        for forward_jump in forward_jump_edge:
            if forward_jump.jump_dir == "left":
                x_shift = x_shift_by_forward_jump(np.array([forward_jump.dest_area.right_y - forward_jump.start_area.left_y]))
                samplep = np.linspace(forward_jump.start_area.left_x - x_shift, forward_jump.start_area.left_x)
                self.ax.draw_artist(self.ax.plot(samplep, forward_jump.start_area.left_y - y_shift_by_x(-samplep + forward_jump.start_area.left_x))[0])
                self.ax.draw_artist(self.ax.text(forward_jump.start_area.left_x, forward_jump.start_area.left_y, f"{i}", verticalalignment="center"))
            else:
                x_shift = x_shift_by_forward_jump(np.array([forward_jump.dest_area.left_y - forward_jump.start_area.right_y]))
                samplep = np.linspace(forward_jump.start_area.right_x, forward_jump.start_area.right_x + x_shift)
                self.ax.draw_artist(self.ax.plot(samplep, forward_jump.start_area.right_y - y_shift_by_x(samplep - forward_jump.start_area.right_x))[0])
                self.ax.draw_artist(self.ax.text(forward_jump.start_area.right_x, forward_jump.start_area.right_y, f"{i}", verticalalignment="center"))
            i += 1
        self.fig.canvas.blit(self.fig.bbox)
        self.fig.canvas.flush_events()
        sleep(10)





    def plot_direct_jump(self, direct_jump_edge, show_index=False):
        cmap = mpl.cm.tab20c
        self.fig.canvas.restore_region(self.bg)
        i = 0
        for direct_jump in direct_jump_edge:
            if direct_jump.jump_dir == "left":
                start_y = direct_jump.start_area.y_at_location_x(direct_jump.dest_area.right_x)
                x_shift = x_shift_by_forward_jump(np.array([direct_jump.dest_area.right_y - start_y]))
                samplep = np.linspace(direct_jump.dest_area.right_x, direct_jump.dest_area.right_x + x_shift)
                self.ax.draw_artist(self.ax.plot(samplep, start_y - y_shift_by_x(-samplep + direct_jump.dest_area.right_x + x_shift))[0])
                if show_index:
                    self.ax.draw_artist(self.ax.text(direct_jump.dest_area.right_x, direct_jump.dest_area.right_y, f"{i}", verticalalignment="center"))
            if direct_jump.jump_dir == "right":
                start_y = direct_jump.start_area.y_at_location_x(direct_jump.dest_area.left_x)
                x_shift = x_shift_by_forward_jump(np.array([direct_jump.dest_area.left_y - start_y]))
                samplep = np.linspace(direct_jump.dest_area.left_x - x_shift, direct_jump.dest_area.left_x)
                self.ax.draw_artist(self.ax.plot(samplep, start_y - y_shift_by_x(samplep - direct_jump.dest_area.left_x +x_shift))[0])
                if show_index:
                    self.ax.draw_artist(self.ax.text(direct_jump.dest_area.left_x, direct_jump.dest_area.left_y, f"{i}", verticalalignment="center"))
            if direct_jump.jump_dir == "straight":
                for sample in np.linspace(direct_jump.start_area.left_x, direct_jump.start_area.right_x, 2):
                    self.ax.draw_artist(self.ax.arrow(sample, direct_jump.start_area.y_at_location_x(sample), 
                             0, direct_jump.dest_area.y_at_location_x(sample) - direct_jump.start_area.y_at_location_x(sample)
                             ,length_includes_head=True, head_width=10))
            i += 1
        self.fig.canvas.blit(self.fig.bbox)
        self.fig.canvas.flush_events()
        sleep(10)





    def plot_ladder(self, ladder_edge, show_index=False):
        cmap = mpl.cm.tab20c
        self.fig.canvas.restore_region(self.bg)
        i = 0
        for ladder in ladder_edge:
            self.ax.draw_artist(self.ax.plot((ladder.x, ladder.x),(ladder.lower_y, ladder.upper_y), color="black")[0])
            if ladder.jump_dir == "straight":
                self.ax.draw_artist(self.ax.plot((ladder.x, ladder.x), (ladder.lower_y, ladder.start_area.y_at_location_x(ladder.x)), color="red")[0])
                if show_index:
                    self.ax.draw_artist(self.ax.text(ladder.x, (ladder.lower_y + ladder.upper_y)/2, f"{i}"))
            elif ladder.jump_dir == "left":
                self.ax.draw_artist(self.ax.plot((ladder.x, ladder.x), (ladder.lower_y, ladder.start_area.y_at_location_x(ladder.x)), color="red")[0])
                self.ax.draw_artist(self.ax.plot((ladder.x, ladder.x - JUMP_ROPE_AWAY_DISTNACE), 
                    (ladder.lower_y, ladder.start_area.y_at_location_x(ladder.x - JUMP_ROPE_AWAY_DISTNACE)), color="red")[0])
                self.ax.draw_artist(self.ax.text(ladder.x, (ladder.lower_y + ladder.upper_y)/2, f"{i}"))
            elif ladder.jump_dir == "right":
                self.ax.draw_artist(self.ax.plot((ladder.x, ladder.x), (ladder.lower_y, ladder.start_area.y_at_location_x(ladder.x)), color="red")[0])
                self.ax.draw_artist(self.ax.plot((ladder.x, ladder.x + JUMP_ROPE_AWAY_DISTNACE), 
                    (ladder.lower_y, ladder.start_area.y_at_location_x(ladder.x + JUMP_ROPE_AWAY_DISTNACE)), color="red")[0])
                if show_index:
                    self.ax.draw_artist(self.ax.text(ladder.x, (ladder.lower_y + ladder.upper_y)/2, f"{i}"))
            elif ladder.jump_dir == "both":
                self.ax.draw_artist(self.ax.plot((ladder.x, ladder.x), (ladder.lower_y, ladder.start_area.y_at_location_x(ladder.x)), color="red")[0])
                self.ax.draw_artist(self.ax.plot((ladder.x, ladder.x - JUMP_ROPE_AWAY_DISTNACE), 
                    (ladder.lower_y, ladder.start_area.y_at_location_x(ladder.x - JUMP_ROPE_AWAY_DISTNACE)), color="red")[0])
                self.ax.draw_artist(self.ax.plot((ladder.x, ladder.x + JUMP_ROPE_AWAY_DISTNACE), 
                    (ladder.lower_y, ladder.start_area.y_at_location_x(ladder.x + JUMP_ROPE_AWAY_DISTNACE)), color="red")[0])
                if show_index:
                    self.ax.draw_artist(self.ax.text(ladder.x, (ladder.lower_y + ladder.upper_y)/2, f"{i}"))
            i+=1
        self.fig.canvas.blit(self.fig.bbox)
        self.fig.canvas.flush_events()
        sleep(10)


    # def plot_