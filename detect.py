import torch
from torchvision import transforms
from PIL import Image, ImageDraw
from model import EAST
import os
import numpy as np
import lanms
from utils import *

def resize_img(image):
    '''resize image to be divisible by 32
    '''
    # w, h = img.size
    # resize_w = w
    # resize_h = h
    #
    # resize_h = resize_h if resize_h % 32 == 0 else int(resize_h / 32) * 32
    # resize_w = resize_w if resize_w % 32 == 0 else int(resize_w / 32) * 32
    # img = img.resize((resize_w, resize_h), Image.BILINEAR)
    # ratio_h = resize_h / h
    # ratio_w = resize_w / w
    new_dimensions = (126, 224)
    old_height, old_width = image.height, image.width
    new_height, new_width = new_dimensions
    ratio_height, ratio_width = new_height / old_height, new_width / old_width

    resized_image = image.resize((new_width, new_height), Image.BILINEAR)

    return image, ratio_height, ratio_width


def load_pil(img):
    '''convert PIL Image to torch.Tensor
    '''
    t = transforms.Compose([transforms.ToTensor(),
                            transforms.Normalize((0.5,), (0.5,))])
    return t(img)


# def is_valid_poly(res, score_shape, scale):
#     '''check if the poly in image scope
#     Input:
#         res        : restored poly in original image
#         score_shape: score map shape
#         scale      : feature map -> image
#     Output:
#         True if valid
#     '''
#     cnt = 0
#     for i in range(len(res)):
#         if res[i % 4] < 0 or res[i % 4] >= score_shape[0] * scale or \
#            res[(i % 4) + 4] < 0 or res[(i % 4) + 4] >= score_shape[1] * scale:
#             cnt += 1
#     return True if cnt <= 1 else False

def is_valid_poly(res, score_shape, scale):
	'''check if the poly in image scope
	Input:
		res        : restored poly in original image
		score_shape: score map shape
		scale      : feature map -> image
	Output:
		True if valid
	'''
	cnt = 0
	for i in range(res.shape[1]):
		if res[0,i] < 0 or res[0,i] >= score_shape[1] * scale or \
           res[1,i] < 0 or res[1,i] >= score_shape[0] * scale:
			cnt += 1
	return True if cnt <= 1 else False


# def restore_polys(valid_pos, valid_geo, score_shape, scale=4):
#     polys = []
#     index = []
#     valid_pos *= scale
#     d = valid_geo[:8, :]
#
#     for i in range(valid_pos.shape[0]):
#         x = valid_pos[i, 0]
#         y = valid_pos[i, 1]
#         x_1 = x + d[0, i]
#         y_1 = y + d[1, i]
#         x_2 = x + d[2, i]
#         y_2 = y + d[3, i]
#         x_3 = x + d[4, i]
#         y_3 = y + d[5, i]
#         x_4 = x + d[6, i]
#         y_4 = y + d[7, i]
#
#         coordinates = [x_1, y_1, x_2, y_2, x_3, y_3, x_4, y_4]
#
#         if is_valid_poly(coordinates, score_shape, scale):
#             index.append(i)
#             polys.append(coordinates)
#
#     return np.array(polys), index
def Get_Rotation_Matrix(angle):
    return np.array([[math.cos(angle), -math.sin(angle)], [math.sin(angle), math.cos(angle)]])

def restore_polys(valid_pos, valid_geo, score_shape, scale=4):
	'''restore polys from feature maps in given positions
	Input:
		valid_pos  : potential text positions <numpy.ndarray, (n,2)>
		valid_geo  : geometry in valid_pos <numpy.ndarray, (5,n)>
		score_shape: shape of score map
		scale      : image / feature map
	Output:
		restored polys <numpy.ndarray, (n,8)>, index
	'''
	polys = []
	index = []
	valid_pos *= scale
	d = valid_geo[:4, :] # 4 x N
	angle = valid_geo[4, :] # N,

	for i in range(valid_pos.shape[0]):
		x = valid_pos[i, 0]
		y = valid_pos[i, 1]
		y_min = y - d[0, i]
		y_max = y + d[1, i]
		x_min = x - d[2, i]
		x_max = x + d[3, i]
		rotate_mat = Get_Rotation_Matrix(-angle[i])

		temp_x = np.array([[x_min, x_max, x_max, x_min]]) - x
		temp_y = np.array([[y_min, y_min, y_max, y_max]]) - y
		coordidates = np.concatenate((temp_x, temp_y), axis=0)
		res = np.dot(rotate_mat, coordidates)
		res[0,:] += x
		res[1,:] += y

		if is_valid_poly(res, score_shape, scale):
			index.append(i)
			polys.append([res[0,0], res[1,0], res[0,1], res[1,1], res[0,2], res[1,2],res[0,3], res[1,3]])
	return np.array(polys), index

# def get_boxes(score, geo, score_thresh=0.9, nms_thresh=0.2):
#     # score = score[0,:,:]
#     xy_text = np.argwhere(score > score_thresh)
#     if xy_text.size == 0:
#         # print('No text detected')
#         return None
#
#     xy_text = xy_text[np.argsort(xy_text[:,0])]
#     valid_pos = xy_text[:, ::-1].copy()
#     valid_geo = geo[:, xy_text[:, 0], xy_text[:, 1]] #quad has 8 channels
#     polys_restored, index = restore_polys(valid_pos, valid_geo, score.shape)
#     if polys_restored.size == 0:
#         # print('poly here')
#         polys_restored = [[377,117,463,117,465,130,378,130], [493,115,519,115,519,131,493,131], [374,155,409,155,409,170,374,170]]
#         polys_restored = np.array(polys_restored)
#         index = [0, 1, 2]
#     boxes = np.zeros((polys_restored.shape[0], 9), dtype=np.float32)
#     boxes[:, :8] = polys_restored
#     #boxes[:, 8] = score[xy_text[index, 0], xy_text[index, 1]]
#     boxes = lanms.merge_quadrangle_n9(boxes.astype('float32'), nms_thresh)
#     return boxes[:, :8]

def get_boxes(score, geo, score_thresh=0.9, nms_thresh=0.2):
	'''get boxes from feature map
	Input:
		score       : score map from model <numpy.ndarray, (1,row,col)>
		geo         : geo map from model <numpy.ndarray, (5,row,col)>
		score_thresh: threshold to segment score map
		nms_thresh  : threshold in nms
	Output:
		boxes       : final polys <numpy.ndarray, (n,9)>
	'''
	score = score[0,:,:]
	xy_text = np.argwhere(score > score_thresh) # n x 2, format is [r, c]
	if xy_text.size == 0:
		return None

	xy_text = xy_text[np.argsort(xy_text[:, 0])]
	valid_pos = xy_text[:, ::-1].copy() # n x 2, [x, y]
	valid_geo = geo[:, xy_text[:, 0], xy_text[:, 1]] # 5 x n
	polys_restored, index = restore_polys(valid_pos, valid_geo, score.shape)
	if polys_restored.size == 0:
		return None

	boxes = np.zeros((polys_restored.shape[0], 9), dtype=np.float32)
	boxes[:, :8] = polys_restored
	boxes[:, 8] = score[xy_text[index, 0], xy_text[index, 1]]
	boxes = lanms.merge_quadrangle_n9(boxes.astype('float32'), nms_thresh)
    # return boxes
	return boxes[:, :8]


def adjust_ratio(boxes, ratio_w, ratio_h):
	'''refine boxes
	Input:
		boxes  : detected polys <numpy.ndarray, (n,9)>
		ratio_w: ratio of width
		ratio_h: ratio of height
	Output:
		refined boxes
	'''
	if boxes is None or boxes.size == 0:
		return None
	boxes[:,[0,2,4,6]] /= ratio_w
	boxes[:,[1,3,5,7]] /= ratio_h
	return np.around(boxes)

# def detect(img, score, geo):
#     '''detect text regions of img using model
#     Input:
#         img   : PIL Image
#         model : detection model
#         device: gpu if gpu is available
#     Output:
#         detected polys
#     '''
#     img, ratio_h, ratio_w = resize_img(img)
#     with torch.no_grad():
#         score, geo = model(load_pil(img).to(device))
#     boxes = get_boxes(score.squeeze(0).detach().numpy(), geo.squeeze(0).detach().numpy())
#     boxes = adjust_ratio(boxes, ratio_w=1, ratio_h=1)
#     return boxes
#     return adjust_ratio(boxes, ratio_w, ratio_h)

def detect(img, model, device):
	'''detect text regions of img using model
	Input:
		img   : PIL Image
		model : detection model
		device: gpu if gpu is available
	Output:
		detected polys
	'''
	img, ratio_h, ratio_w = resize_img(img)
	with torch.no_grad():
		score, geo = model(load_pil(img).to(device))
	boxes = get_boxes(score.squeeze(0).cpu().numpy(), geo.squeeze(0).cpu().numpy())
	return adjust_ratio(boxes, ratio_w, ratio_h)


def plot_boxes(img, boxes):
    '''plot boxes on image
    '''
    if boxes is None:
        return img

    draw = ImageDraw.Draw(img)
    for box in boxes:
        draw.polygon([box[0], box[1], box[2], box[3], box[4], box[5], box[6], box[7]], outline=(255))
    return img


def detect_dataset(model, device, test_img_path, submit_path):
    '''detection on whole dataset, save .txt results in submit_path
    Input:
        model        : detection model
        device       : gpu if gpu is available
        test_img_path: dataset path
        submit_path  : submit result for evaluation
    '''
    img_files = os.listdir(test_img_path)
    img_files = sorted([os.path.join(test_img_path, img_file) for img_file in img_files])

    for i, img_file in enumerate(img_files):
        print('evaluating {} image'.format(i), end='\r')
        boxes = detect(Image.open(img_file), model, device)
        seq = []
        if boxes is not None:
            seq.extend([','.join([str(int(b)) for b in box[:-1]]) + '\n' for box in boxes])
        with open(os.path.join(submit_path, 'res_' + os.path.basename(img_file).replace('.jpg','.txt')), 'w') as f:
            f.writelines(seq)


# if __name__ == '__main__':
#     boxes = detect(img, model, device)
#     plot_img = plot_boxes(img, boxes)
#     #plot_img.save(res_img)
#     img_path    = '../ICDAR_2015/test_img/img_2.jpg'
# 	model_path  = './pths/east_vgg16.pth'
# 	res_img     = './res.bmp'
# 	device = torch.device("cuda:0" if torch.cuda.is_available() else "cpu")
# 	model = EAST().to(device)
# 	model.load_state_dict(torch.load(model_path))
# 	model.eval()
# 	img = Image.open(img_path)
#
# 	boxes = detect(img, model, device)
# 	plot_img = plot_boxes(img, boxes)
# 	plot_img.save(res_img)
