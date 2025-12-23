# Labelme 项目关键技术文档

## 项目概述

Labelme 是一个使用 Python 和 Qt 编写的图像标注工具，专注于多边形图像标注。它提供了一个强大的图形编辑器，支持多种图形类型（多边形、矩形、圆形、线、点等）的创建和编辑。

**核心特性：**
- 矢量图形标注（多边形、矩形、圆、线、点）
- AI 辅助标注（基于 SAM/SAM2 模型）
- 支持实例分割和语义分割
- 导出为 VOC 和 COCO 格式
- 视频帧标注支持

## 技术栈

### 核心依赖

```toml
# 从 pyproject.toml 中提取的关键依赖
PyQt5 >= 5.14.0          # GUI 框架
numpy                     # 数值计算
Pillow >= 2.8            # 图像处理
imgviz                   # 图像可视化工具
scikit-image             # 图像处理算法
osam >= 0.2.5            # AI 模型集成（SAM/SAM2）
matplotlib               # 绘图库
natsort >= 7.1.0         # 自然排序
```

## 1. 编辑器核心技术

### 1.1 架构设计

Labelme 采用经典的 MVC 架构模式：

```
┌─────────────────────────────────────┐
│         MainWindow (app.py)          │  ← 主窗口控制器
│   - 菜单/工具栏管理                   │
│   - 文件操作                          │
│   - 标签管理                          │
└──────────────┬──────────────────────┘
               │
               ├─────────────────────────┐
               │                         │
       ┌───────▼──────┐          ┌──────▼───────┐
       │    Canvas     │          │   Widgets    │
       │ (canvas.py)   │          │   组件集合    │
       │ 1200+ 行代码   │          │              │
       └───────┬───────┘          └──────────────┘
               │
         ┌─────▼─────┐
         │   Shape   │  ← 矢量图形数据模型
         │(shape.py) │
         └───────────┘
```

### 1.2 Canvas 画布编辑器

Canvas 是整个编辑器的核心组件（`widgets/canvas.py`），继承自 `QtWidgets.QWidget`，提供了完整的图形交互功能。

#### 核心类设计

```python
class Canvas(QtWidgets.QWidget):
    # 状态管理
    mode: CanvasMode  # EDIT 或 CREATE 模式
    _createMode: str  # 创建模式：polygon, rectangle, circle, line, point, etc.
    
    # 图形管理
    shapes: list[Shape]              # 所有图形对象
    shapesBackups: list[list[Shape]] # 撤销/重做栈
    current: Shape | None            # 当前正在创建的图形
    selectedShapes: list[Shape]       # 选中的图形
    
    # 交互状态
    hShape: Shape | None    # 鼠标悬停的图形
    hVertex: int | None     # 鼠标悬停的顶点索引
    hEdge: int | None       # 鼠标悬停的边索引
    
    # 渲染和缩放
    pixmap: QtGui.QPixmap   # 背景图像
    scale: float            # 缩放比例
    epsilon: float          # 顶点和边的捕捉距离（默认 10.0）
```

#### 关键绘制流程

Labelme 使用 Qt 的 `QPainter` 进行高质量渲染：

```python
def paintEvent(self, event: QtGui.QPaintEvent) -> None:
    p = self._painter
    p.begin(self)
    
    # 启用抗锯齿和高质量渲染
    p.setRenderHint(QtGui.QPainter.Antialiasing)
    p.setRenderHint(QtGui.QPainter.HighQualityAntialiasing)
    p.setRenderHint(QtGui.QPainter.SmoothPixmapTransform)
    
    # 应用缩放和平移变换
    p.scale(self.scale, self.scale)
    p.translate(self.offsetToCenter())
    
    # 绘制背景图像
    p.drawPixmap(0, 0, self.pixmap)
    
    # 绘制所有图形
    Shape.scale = self.scale
    for shape in self.shapes:
        if (shape.selected or not self._hideBackround) and self.isVisible(shape):
            shape.fill = shape.selected or shape == self.hShape
            shape.paint(p)
    
    # 绘制当前正在创建的图形
    if self.current:
        self.current.paint(p)
        self.line.paint(p)  # 临时辅助线
```

### 1.3 坐标系统与变换

Canvas 实现了完整的坐标变换系统，支持缩放和平移：

```python
def transformPos(self, point: QPointF) -> QPointF:
    """从控件逻辑坐标转换为画家逻辑坐标"""
    return point / self.scale - self.offsetToCenter()

def offsetToCenter(self) -> QPointF:
    """计算图像居中偏移量"""
    s = self.scale
    area = super().size()
    w, h = self.pixmap.width() * s, self.pixmap.height() * s
    aw, ah = area.width(), area.height()
    x = (aw - w) / (2 * s) if aw > w else 0
    y = (ah - h) / (2 * s) if ah > h else 0
    return QPointF(x, y)
```

**坐标空间层次：**
1. **屏幕坐标** → 鼠标事件的原始坐标
2. **控件坐标** → 相对于 Canvas 控件的坐标  
3. **图像坐标** → 经过缩放和平移变换后的实际图像坐标

### 1.4 交互模式

Canvas 支持两种主要模式：

#### EDIT 模式 - 编辑现有图形
- **选择图形**：点击图形或顶点
- **移动图形**：拖动选中的图形
- **移动顶点**：拖动选中的顶点
- **添加顶点**：`Alt + Click` 边缘
- **删除顶点**：`Alt + Shift + Click` 顶点
- **复制图形**：右键拖动

#### CREATE 模式 - 创建新图形

支持多种创建模式：

| 模式 | 描述 | 完成方式 |
|------|------|---------|
| `polygon` | 多边形 | 双击或回到起点 |
| `rectangle` | 矩形 | 两点确定 |
| `circle` | 圆形 | 中心点 + 半径点 |
| `line` | 直线 | 起点 + 终点 |
| `point` | 点 | 单击 |
| `linestrip` | 折线 | Ctrl+Click 结束 |
| `ai_polygon` | AI 多边形 | AI 辅助 + Ctrl+Click |
| `ai_mask` | AI 掩码 | AI 辅助 + Ctrl+Click |

### 1.5 鼠标事件处理

Canvas 实现了精细的鼠标事件处理：

```python
def mouseMoveEvent(self, ev):
    pos = self.transformPos(ev.localPos())
    
    # 1. 拖拽画布（中键）
    if self._is_dragging:
        delta = pos - self._dragging_start_pos
        self.scrollRequest.emit(int(delta.x()), Qt.Horizontal)
        return
    
    # 2. 绘制模式 - 更新临时线
    if self.drawing():
        if self.createMode == "polygon":
            self.line.points = [self.current[-1], pos]
        # ... 其他模式的处理
        self.repaint()
        return
    
    # 3. 编辑模式 - 高亮和拖动
    if self.editing():
        # 查找最近的顶点
        index = shape.nearestVertex(pos, self.epsilon)
        if index is not None:
            self.hVertex = index
            shape.highlightVertex(index, shape.MOVE_VERTEX)
        # 查找最近的边
        elif index_edge is not None:
            self.hEdge = index_edge
        # 检查是否在图形内部
        elif shape.containsPoint(pos):
            self.hShape = shape
```

## 2. 矢量图形技术

### 2.1 Shape 类 - 矢量图形核心

Shape 类（`shape.py`）是所有矢量图形的基础数据模型：

```python
class Shape:
    # 样式配置（类变量）
    line_color: QtGui.QColor          # 边框颜色
    fill_color: QtGui.QColor          # 填充颜色
    vertex_fill_color: QtGui.QColor   # 顶点颜色
    select_line_color: QtGui.QColor   # 选中边框颜色
    select_fill_color: QtGui.QColor   # 选中填充颜色
    
    # 几何数据
    points: list[QPointF]       # 顶点坐标列表
    point_labels: list[int]     # 顶点标签（用于 AI 模式，1=包含，0=排除）
    shape_type: str             # polygon, rectangle, circle, line, etc.
    mask: np.ndarray | None     # 掩码数据（AI 模式）
    
    # 元数据
    label: str                  # 标签名
    group_id: int | None        # 分组 ID
    flags: dict                 # 标志
    description: str            # 描述
```

### 2.2 图形绘制算法

Shape 实现了针对不同图形类型的优化绘制：

```python
def paint(self, painter):
    # 1. 设置画笔
    color = self.select_line_color if self.selected else self.line_color
    pen = QtGui.QPen(color)
    pen.setWidth(self.PEN_WIDTH)
    painter.setPen(pen)
    
    # 2. 绘制掩码（如果存在）
    if self.mask is not None:
        # 将掩码转换为图像并绘制
        image_to_draw = np.zeros(self.mask.shape + (4,), dtype=np.uint8)
        image_to_draw[self.mask] = fill_color
        qimage = QtGui.QImage.fromData(img_arr_to_data(image_to_draw))
        painter.drawImage(self._scale_point(self.points[0]), qimage)
        
        # 使用 skimage 查找轮廓并绘制边界
        contours = skimage.measure.find_contours(np.pad(self.mask, pad_width=1))
        for contour in contours:
            # ... 绘制轮廓路径
    
    # 3. 绘制矢量路径
    if self.shape_type == "rectangle":
        rectangle = QtCore.QRectF(
            self._scale_point(self.points[0]),
            self._scale_point(self.points[1])
        )
        line_path.addRect(rectangle)
    
    elif self.shape_type == "circle":
        radius = distance(self._scale_point(self.points[0] - self.points[1]))
        line_path.addEllipse(self._scale_point(self.points[0]), radius, radius)
    
    elif self.shape_type in ["polygon", "linestrip"]:
        line_path.moveTo(self._scale_point(self.points[0]))
        for p in self.points:
            line_path.lineTo(self._scale_point(p))
    
    # 4. 绘制路径和顶点
    painter.drawPath(line_path)
    painter.drawPath(vrtx_path)
    
    # 5. 填充（如果需要）
    if self.fill:
        painter.fillPath(line_path, fill_color)
```

### 2.3 几何计算

Shape 提供了丰富的几何计算功能：

#### 最近顶点查找

```python
def nearestVertex(self, point, epsilon):
    """查找距离点最近且在 epsilon 范围内的顶点"""
    min_distance = float("inf")
    min_i = None
    point = QtCore.QPointF(point.x() * self.scale, point.y() * self.scale)
    for i, p in enumerate(self.points):
        p = QtCore.QPointF(p.x() * self.scale, p.y() * self.scale)
        dist = labelme.utils.distance(p - point)
        if dist <= epsilon and dist < min_distance:
            min_distance = dist
            min_i = i
    return min_i
```

#### 最近边查找

```python
def nearestEdge(self, point, epsilon):
    """查找距离点最近且在 epsilon 范围内的边"""
    min_distance = float("inf")
    post_i = None
    for i in range(len(self.points)):
        start = self.points[i - 1]
        end = self.points[i]
        # 计算点到线段的距离
        dist = labelme.utils.distancetoline(point, [start, end])
        if dist <= epsilon and dist < min_distance:
            min_distance = dist
            post_i = i
    return post_i
```

#### 点在图形内判断

```python
def containsPoint(self, point) -> bool:
    """判断点是否在图形内部"""
    if self.shape_type in ["line", "linestrip", "points"]:
        return False  # 线和点不考虑内部
    
    # 对于掩码类型，直接查询掩码
    if self.mask is not None:
        y = np.clip(int(round(point.y() - self.points[0].y())), 
                    0, self.mask.shape[0] - 1)
        x = np.clip(int(round(point.x() - self.points[0].x())), 
                    0, self.mask.shape[1] - 1)
        return self.mask[y, x]
    
    # 使用 Qt 的路径包含检测
    return self.makePath().contains(point)
```

### 2.4 矢量编辑操作

#### 添加顶点

```python
def addPoint(self, point, label=1):
    """添加新顶点"""
    if self.points and point == self.points[0]:
        self.close()  # 闭合多边形
    else:
        self.points.append(point)
        self.point_labels.append(label)
```

#### 插入顶点

```python
def insertPoint(self, i, point, label=1):
    """在指定位置插入顶点（用于边上添加点）"""
    self.points.insert(i, point)
    self.point_labels.insert(i, label)
```

#### 删除顶点

```python
def removePoint(self, i: int):
    """删除指定顶点"""
    if not self.canRemovePoint():
        return  # 保持最小顶点数
    self.points.pop(i)
    self.point_labels.pop(i)

def canRemovePoint(self) -> bool:
    """检查是否可以删除顶点"""
    if self.shape_type == "polygon" and len(self.points) <= 3:
        return False  # 多边形至少3个顶点
    if self.shape_type == "linestrip" and len(self.points) <= 2:
        return False  # 折线至少2个顶点
    return True
```

#### 移动操作

```python
def moveBy(self, offset):
    """移动整个图形"""
    self.points = [p + offset for p in self.points]

def moveVertexBy(self, i, offset):
    """移动单个顶点"""
    self.points[i] = self.points[i] + offset
```

## 3. AI 辅助编辑技术

### 3.1 集成 SAM/SAM2 模型

Labelme 通过 `osam` 库集成了 Segment Anything Model (SAM)，提供智能分割功能：

```python
def _get_ai_model(self) -> osam.types.Model:
    """获取或缓存 AI 模型"""
    if self._ai_model_cache and self._ai_model_cache.name == self._ai_model_name:
        return self._ai_model_cache
    
    model_type = osam.apis.get_model_type_by_name(self._ai_model_name)
    self._ai_model_cache = model_type()
    return self._ai_model_cache

def _get_ai_image_embedding(self) -> osam.types.ImageEmbedding:
    """获取或缓存图像嵌入"""
    qimage = self.pixmap.toImage()
    
    # 计算缓存键（基于图像内容哈希）
    cache_key = f"{self._ai_model_name}_{pixmap_hash()}"
    
    # 查找缓存
    for key, image_embedding in self._ai_image_embedding_cache:
        if key == cache_key:
            return image_embedding
    
    # 计算新的嵌入
    image = labelme.utils.img_qt_to_arr(img_qt=qimage)
    image_embedding = self._get_ai_model().encode_image(image=imgviz.asrgb(image))
    self._ai_image_embedding_cache.append((cache_key, image_embedding))
    return image_embedding
```

### 3.2 AI 多边形和掩码生成

AI 模式支持两种输出：

#### AI-Polygon 模式

用户点击正样本点（包含）和负样本点（排除），系统生成多边形近似：

```python
def _update_shape_with_sam(
    sam: osam.types.Model,
    image_embedding: osam.types.ImageEmbedding,
    shape: Shape,
    createMode: Literal["ai_polygon", "ai_mask"],
):
    # 分离正负样本点
    point_coords = []
    point_labels = []
    for point, label in zip(shape.points, shape.point_labels):
        point_coords.append([point.x(), point.y()])
        point_labels.append(label)
    
    # 使用 SAM 生成掩码
    masks, scores = sam.generate_masks(
        image_embedding=image_embedding,
        point_coords=point_coords,
        point_labels=point_labels,
    )
    
    # 选择最佳掩码
    best_mask = masks[np.argmax(scores)]
    
    if createMode == "ai_polygon":
        # 将掩码转换为多边形
        polygon = polygon_from_mask.compute_polygon_from_mask(best_mask)
        shape.setShapeRefined(
            shape_type="polygon",
            points=[QPointF(x, y) for x, y in polygon],
            point_labels=[1] * len(polygon),
        )
    elif createMode == "ai_mask":
        # 保存掩码
        shape.setShapeRefined(
            shape_type="mask",
            points=shape.points[:2],  # 包围盒
            point_labels=[1, 1],
            mask=best_mask
        )
```

### 3.3 掩码到多边形转换算法

使用 scikit-image 的轮廓查找和多边形近似：

```python
def compute_polygon_from_mask(mask: np.ndarray) -> np.ndarray:
    """将二值掩码转换为多边形"""
    # 1. 查找轮廓（使用 marching squares 算法）
    contours = skimage.measure.find_contours(np.pad(mask, pad_width=1))
    
    if len(contours) == 0:
        return np.empty((0, 2), dtype=np.float32)
    
    # 2. 选择最长的轮廓
    contour = max(contours, key=_get_contour_length)
    
    # 3. 多边形近似（Douglas-Peucker 算法）
    POLYGON_APPROX_TOLERANCE = 0.004
    polygon = skimage.measure.approximate_polygon(
        coords=contour,
        tolerance=np.ptp(contour, axis=0).max() * POLYGON_APPROX_TOLERANCE,
    )
    
    # 4. 裁剪到图像边界
    polygon = np.clip(polygon, (0, 0), (mask.shape[0] - 1, mask.shape[1] - 1))
    
    # 5. 移除重复的首末点
    polygon = polygon[:-1]
    
    # 6. 坐标转换 yx → xy
    return polygon[:, ::-1]
```

**关键算法：**
- **Marching Squares** - 轮廓提取
- **Douglas-Peucker** - 多边形简化，减少顶点数量同时保持形状

### 3.4 文本检测 (YOLO-World)

通过 YOLO-World 实现基于文本提示的目标检测：

```python
def get_bboxes_from_texts(
    model: str, 
    image: np.ndarray, 
    texts: list[str]
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """根据文本提示检测目标边界框"""
    request = osam.types.GenerateRequest(
        model=model,
        image=image,
        prompt=osam.types.Prompt(
            texts=texts,
            iou_threshold=1.0,
            score_threshold=0.01,
            max_annotations=1000,
        ),
    )
    
    response = osam.apis.generate(request=request)
    
    # 提取边界框、置信度和标签
    boxes = []
    scores = []
    labels = []
    for annotation in response.annotations:
        boxes.append([
            annotation.bounding_box.xmin,
            annotation.bounding_box.ymin,
            annotation.bounding_box.xmax,
            annotation.bounding_box.ymax,
        ])
        scores.append(annotation.score)
        labels.append(texts.index(annotation.text))
    
    return np.array(boxes), np.array(scores), np.array(labels)
```

## 4. 数据持久化

### 4.1 JSON 格式

Labelme 使用 JSON 格式存储标注：

```json
{
  "version": "5.10.0",
  "flags": {},
  "shapes": [
    {
      "label": "person",
      "points": [[100, 150], [200, 150], [200, 300], [100, 300]],
      "group_id": null,
      "description": "",
      "shape_type": "polygon",
      "flags": {},
      "mask": null
    }
  ],
  "imagePath": "image.jpg",
  "imageData": "base64_encoded_image_data_or_null",
  "imageHeight": 480,
  "imageWidth": 640
}
```

### 4.2 LabelFile 类

```python
class LabelFile:
    """处理标注文件的读写"""
    
    def __init__(self, filename=None):
        self.shapes: list[ShapeDict] = []
        self.imagePath: str | None = None
        self.imageData: bytes | None = None
        
    def save(self, filename, shapes, imagePath, 
             imageData=None, imageHeight=None, imageWidth=None,
             otherData=None, flags=None):
        """保存标注到 JSON 文件"""
        data = {
            "version": __version__,
            "flags": flags or {},
            "shapes": shapes,
            "imagePath": imagePath,
            "imageData": imageData,
            "imageHeight": imageHeight,
            "imageWidth": imageWidth,
        }
        if otherData is not None:
            data.update(otherData)
        
        with open(filename, "w") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    
    def load(self, filename):
        """从 JSON 文件加载标注"""
        with open(filename, "r") as f:
            data = json.load(f)
        
        self.shapes = data["shapes"]
        self.imagePath = data.get("imagePath")
        self.imageData = data.get("imageData")
        # ...
```

### 4.3 矢量转栅格

将矢量标注转换为分割掩码：

```python
def shape_to_mask(
    img_shape: tuple[int, ...],
    points: list[list[float]],
    shape_type: str = None,
) -> np.ndarray:
    """将矢量图形转换为二值掩码"""
    mask = PIL.Image.fromarray(np.zeros(img_shape[:2], dtype=np.uint8))
    draw = PIL.ImageDraw.Draw(mask)
    xy = [tuple(point) for point in points]
    
    if shape_type == "circle":
        (cx, cy), (px, py) = xy
        d = math.sqrt((cx - px) ** 2 + (cy - py) ** 2)
        draw.ellipse([cx - d, cy - d, cx + d, cy + d], outline=1, fill=1)
    
    elif shape_type == "rectangle":
        draw.rectangle(xy, outline=1, fill=1)
    
    elif shape_type in [None, "polygon"]:
        draw.polygon(xy=xy, outline=1, fill=1)
    
    return np.array(mask, dtype=bool)
```

## 5. 性能优化技术

### 5.1 撤销/重做栈

```python
def storeShapes(self):
    """保存当前状态到撤销栈"""
    shapesBackup = [shape.copy() for shape in self.shapes]
    
    # 限制栈大小（默认 10 层）
    if len(self.shapesBackups) > self.num_backups:
        self.shapesBackups = self.shapesBackups[-self.num_backups - 1:]
    
    self.shapesBackups.append(shapesBackup)

def restoreShape(self):
    """恢复上一个状态"""
    if not self.isShapeRestorable:
        return
    
    self.shapesBackups.pop()  # 移除当前状态
    shapesBackup = self.shapesBackups.pop()
    self.shapes = shapesBackup
```

### 5.2 AI 模型缓存

使用 LRU 缓存策略减少重复计算：

```python
# 图像嵌入缓存（最多缓存 3 张图像）
self._ai_image_embedding_cache = collections.deque(maxlen=3)

# 模型缓存（单例）
self._ai_model_cache: osam.types.Model | None = None
```

### 5.3 部分重绘优化

Canvas 使用 Qt 的事件系统实现按需重绘：

```python
# 仅在必要时触发重绘
self.update()  # 异步重绘请求
self.repaint()  # 同步强制重绘
```

## 6. 关键设计模式

### 6.1 观察者模式（信号-槽）

```python
class Canvas(QtWidgets.QWidget):
    # 定义信号
    zoomRequest = QtCore.pyqtSignal(int, QPointF)
    selectionChanged = QtCore.pyqtSignal(list)
    newShape = QtCore.pyqtSignal()
    shapeMoved = QtCore.pyqtSignal()
    
    # 发射信号
    self.newShape.emit()
    self.selectionChanged.emit(shapes)
```

### 6.2 命令模式（撤销/重做）

通过状态快照实现：

```python
# 保存状态
self.storeShapes()

# 恢复状态
self.restoreShape()
```

### 6.3 策略模式（创建模式）

不同图形类型使用不同的创建策略：

```python
if self.createMode == "polygon":
    # 多边形策略
elif self.createMode == "rectangle":
    # 矩形策略
elif self.createMode == "ai_polygon":
    # AI 多边形策略
```

## 7. 核心技术总结

### 编辑器技术要点

1. **PyQt5 GUI 框架** - 提供完整的桌面应用能力
2. **QPainter 高质量渲染** - 抗锯齿、平滑变换
3. **坐标变换系统** - 支持缩放、平移的多层坐标空间
4. **精细的鼠标交互** - 顶点捕捉、边捕捉、拖拽
5. **信号-槽机制** - 松耦合的事件通信

### 矢量编辑技术要点

1. **统一的 Shape 数据模型** - 支持多种图形类型
2. **QPainterPath 矢量绘制** - 高效的路径渲染
3. **几何计算算法** - 点线距离、点在多边形内判断
4. **顶点和边的智能捕捉** - 基于 epsilon 阈值
5. **矢量与栅格互转** - PIL ImageDraw 绘制掩码

### AI 辅助技术要点

1. **SAM/SAM2 集成** - 实时语义分割
2. **YOLO-World** - 基于文本的目标检测
3. **掩码到多边形转换** - Marching Squares + Douglas-Peucker
4. **模型和嵌入缓存** - 提升性能
5. **正负样本交互** - 精细控制分割结果

### 架构设计亮点

1. **清晰的 MVC 分层** - MainWindow/Canvas/Shape
2. **可扩展的图形类型** - 通过 shape_type 参数化
3. **完善的撤销机制** - 状态快照栈
4. **高性能渲染** - 按需重绘 + 硬件加速
5. **模块化的 AI 集成** - 通过 osam 库解耦

## 8. 代码示例

### 创建自定义图形类型

```python
# 扩展 Shape 支持新的图形类型
class Shape:
    @shape_type.setter
    def shape_type(self, value):
        valid_types = [
            "polygon", "rectangle", "point", "line", 
            "circle", "linestrip", "points", "mask",
            "custom_shape"  # 添加自定义类型
        ]
        if value not in valid_types:
            raise ValueError(f"Unexpected shape_type: {value}")
        self._shape_type = value
```

### 自定义 AI 模型

```python
# 在 Canvas 中切换 AI 模型
canvas.set_ai_model_name("sam2:latest")  # 或 "yoloworld:latest"
```

### 编程式创建标注

```python
from labelme.shape import Shape
from PyQt5.QtCore import QPointF

# 创建多边形
shape = Shape(label="person", shape_type="polygon")
shape.points = [
    QPointF(100, 100),
    QPointF(200, 100),
    QPointF(200, 200),
    QPointF(100, 200),
]
shape.close()

canvas.shapes.append(shape)
canvas.update()
```

## 参考资源

- **项目主页**: https://github.com/wkentaro/labelme
- **PyQt5 文档**: https://doc.qt.io/qtforpython/
- **SAM 论文**: "Segment Anything" (Meta AI, 2023)
- **scikit-image**: https://scikit-image.org/
- **Douglas-Peucker 算法**: https://en.wikipedia.org/wiki/Ramer–Douglas–Peucker_algorithm
