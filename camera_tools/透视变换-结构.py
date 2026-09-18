
import cv2
import numpy as np
import  sys

from fontTools.misc.bezierTools import epsilon
eps = sys.float_info.epsilon
#读取图像
img = cv2.imread("B.jpg")
img_orgin = cv2.imread("B.jpg")
#将原图转为灰度图
gray_img = cv2.cvtColor(img,cv2.COLOR_BGR2GRAY)
max_y,max_x = gray_img.shape[0],gray_img.shape[1]
#Canny边缘检测
canny_img = cv2.Canny(gray_img,350,550,3)
#显示边缘检测后的图像
cv2.imwrite("canny_img.jpg",canny_img)



def draw_line(img,lines):
    # 绘制直线
    for line_points in lines:
        cv2.line(img,(line_points[0][0],line_points[0][1]),(line_points[0][2],line_points[0][3]),
                 (0,255,0),2,8,0)
    cv2.imwrite("line_img.jpg", img)

# #Hough直线检测
lines = cv2.HoughLinesP(canny_img,1,np.pi/180,150,minLineLength=30,maxLineGap=10)
#基于边缘检测的图像来检测直线
draw_line(img,lines)

line_intersect = []
#计算四条直线的交点作为顶点坐标
def computer_intersect_point(lines,):
    def get_line_k_b(line_point):
        """计算直线的斜率和截距
        :param line_point: 直线的坐标点
        :return:
        """
        #获取直线的两点坐标
        x1,y1,x2,y2 = line_point[0]
        #计算直线的斜率和截距
        a1 = y2 - y1
        b1 = x1 - x2
        c1 = a1 * x1 + b1 * y1

        return a1,b1,c1
    #用来存放直线的交点坐标
    line_intersect = []
    for i in range(len(lines)):
        a1,b1,c1 = get_line_k_b(lines[i])
        for j in range(i+1,len(lines)):
            a2,b2,c2 = get_line_k_b(lines[j])
            #计算交点坐标
            det = a1 * b2 - a2 * b1
            if abs(det) < eps :
                continue
            x = (c1 * b2 - c2 * b1) / det
            y = (a1 * c2 - a2 * c1) / det
            if x > 0 and y > 0 and x<=max_x and y<=max_y:
                line_intersect.append((int(np.round(x)),int(np.round(y))))
    return line_intersect
def draw_point(img,points):
    for position in points:
        cv2.circle(img,position,5,(0,0,255),-1)
    cv2.imwrite("draw_point.jpg",img)

#计算直线的交点坐标
line_intersect = computer_intersect_point(lines)
#绘制交点坐标的位置
draw_point(img,line_intersect)


def order_point(points):
    """对交点坐标进行排序
    :param points:
    :return:
    """
    points_array = np.array(points)
    #对x的大小进行排序
    x_sort = np.argsort(points_array[:,0])
    #对y的大小进行排序
    y_sort = np.argsort(points_array[:,1])
    #获取最左边的顶点坐标
    left_point = points_array[x_sort[0]]
    #获取最右边的顶点坐标
    right_point = points_array[x_sort[-1]]
    #获取最上边的顶点坐标
    top_point = points_array[y_sort[0]]
    #获取最下边的顶点坐标
    bottom_point = points_array[y_sort[-1]]
    return np.array([left_point,top_point,right_point,bottom_point],dtype=np.float32)
def target_vertax_point(clockwise_point):
    #计算顶点的宽度(取最大宽度)
    w1 = np.linalg.norm(clockwise_point[0]-clockwise_point[1])
    w2 = np.linalg.norm(clockwise_point[2]-clockwise_point[3])
    w = w1 if w1 > w2 else w2
    #计算顶点的高度(取最大高度)
    h1 = np.linalg.norm(clockwise_point[1]-clockwise_point[2])
    h2 = np.linalg.norm(clockwise_point[3]-clockwise_point[0])
    h = h1 if h1 > h2 else h2
    #将宽和高转换为整数
    w = int(round(w))
    h = int(round(h))
    #计算变换后目标的顶点坐标
    top_left = [0,0]
    top_right = [w,0]
    bottom_right = [w,h]
    bottom_left = [0,h]
    return np.array([top_left,top_right,bottom_right,bottom_left],dtype=np.float32)



def my_getPerspectiveTransform(src_pts, dst_pts):
    """
    手写版 cv2.getPerspectiveTransform（仅适用于 4 对点）。
    参数:
        src_pts : (4,2) ndarray, 原图四个角点 (float或int)
        dst_pts : (4,2) ndarray, 目标四个角点 (float或int)
    返回:
        3x3 Homography 矩阵 (float64)
    """
    src = np.asarray(src_pts, dtype=np.float64).reshape(-1, 2)
    dst = np.asarray(dst_pts, dtype=np.float64).reshape(-1, 2)

    if src.shape != (4, 2) or dst.shape != (4, 2):
        raise ValueError("src_pts and dst_pts 必须都是 4x2 的数组")

    # 构造矩阵 A (8x8) 和向量 b (8,)
    A = []
    b = []
    for (x, y), (xp, yp) in zip(src, dst):
        A.append([x, y, 1, 0, 0, 0, -x * xp, -y * xp])
        A.append([0, 0, 0, x, y, 1, -x * yp, -y * yp])
        b.append(xp)
        b.append(yp)

    A = np.asarray(A, dtype=np.float64)   # (8,8)
    b = np.asarray(b, dtype=np.float64)   # (8,)

    # 直接求解线性方程组（A 必须可逆）
    h = np.linalg.solve(A, b)             # (8,)

    # 把 h 拼成 3x3 矩阵，最后一个元素固定为 1
    H = np.append(h, 1).reshape(3, 3)

    return H


def find_corners(point_list,x_min, y_min,x_max, y_max):
    targets = np.array([[x_min, y_min],
                        [x_max, y_min],
                        [x_max, y_max],
                        [x_min, y_max]], dtype=np.float32)
    points = np.asarray(point_list, dtype=np.float32)

    chosen_idx = []          # 已经被占用的点的索引
    corner_pts = []          # 结果点坐标

    for t in targets:        # 依次处理四个角点
        # 计算所有点到当前目标的欧氏距离的平方（省去 sqrt，加快计算）
        dists = np.sum((points - t) ** 2, axis=1)

        # 把已经被占用的点的距离设为无穷大，保证不会再次被选中
        if chosen_idx:
            dists[chosen_idx] = np.inf

        # 取距离最小的点的索引
        best = int(np.argmin(dists))
        chosen_idx.append(best)
        corner_pts.append(points[best])

    return np.stack(corner_pts), chosen_idx

def find_perspective_corners(x_min, y_min,x_max, y_max):
    targets = np.array([[0, 0],
                        [x_max-x_min, 0],
                        [x_max-x_min, y_max-y_min],
                        [0, y_max-y_min]], dtype=int)
    return np.stack(targets)

#对原始图像的交点坐标进行排序
clockwise_point = order_point(line_intersect)
#获取变换后坐标的位置
target_clockwise_point = target_vertax_point(clockwise_point)


#############
# 取左上角、右下角（整数坐标）
x_min = int(np.min(target_clockwise_point[:, 0]))
y_min = int(np.min(target_clockwise_point[:, 1]))
x_max = int(np.max(target_clockwise_point[:, 0]))
y_max = int(np.max(target_clockwise_point[:, 1]))

cv2.rectangle(img, (x_min, y_min), (x_max, y_max), (255, 0, 0), 2)


x_min = int(np.min(clockwise_point[:, 0]))
y_min = int(np.min(clockwise_point[:, 1]))
x_max = int(np.max(clockwise_point[:, 0]))
y_max = int(np.max(clockwise_point[:, 1]))



# 画矩形（颜色 BGR、线宽 2）
cv2.rectangle(img, (x_min, y_min), (x_max, y_max), (0, 0, 255), 2)

# 为了直观看到结果，可写入文件或直接展示
cv2.imwrite('result_axis_aligned.png', img)
#########################
corner_pts, idx = find_corners(line_intersect,x_min, y_min,x_max, y_max)
target_clockwise_point = find_perspective_corners(x_min, y_min,x_max, y_max)



#计算变换矩阵
# matrix = cv2.getPerspectiveTransform(clockwise_point,target_clockwise_point)
matrix = my_getPerspectiveTransform(corner_pts,target_clockwise_point)

print(matrix)
#计算透视变换后的图片
target_clockwise_point = np.array(target_clockwise_point, dtype=int)
perspective_img = cv2.warpPerspective(img_orgin,matrix,(target_clockwise_point[2][0],target_clockwise_point[2][1]))
cv2.imwrite("perspective_image.jpg", perspective_img)

