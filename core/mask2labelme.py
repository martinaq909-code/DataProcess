import cv2
import numpy as np
import json
import os
import glob
from scipy.spatial.distance import cdist

def find_closest_points(poly1, poly2):
    """
    Find the indices of the closest points between two polygons.
    poly1, poly2: list of [x, y]
    """
    p1 = np.array(poly1)
    p2 = np.array(poly2)
    
    # Compute distance matrix
    dists = cdist(p1, p2)
    
    # Find minimum index
    min_idx = np.unravel_index(np.argmin(dists), dists.shape)
    
    return min_idx[0], min_idx[1] # idx in poly1, idx in poly2

def simplify_points(points, min_dist=5.0):
    """
    Remove points that are too close to each other.
    points: list of [x, y]
    min_dist: minimum distance between consecutive points
    """
    if len(points) < 3:
        return points
        
    new_points = [points[0]]
    for i in range(1, len(points)):
        last_pt = np.array(new_points[-1])
        curr_pt = np.array(points[i])
        dist = np.linalg.norm(curr_pt - last_pt)
        if dist >= min_dist:
            new_points.append(points[i])
            
    # Check closure distance (last point to first point)
    if len(new_points) > 2:
        last_pt = np.array(new_points[-1])
        first_pt = np.array(new_points[0])
        if np.linalg.norm(last_pt - first_pt) < min_dist:
            new_points.pop()
            
    return new_points

def merge_polygons(parent_poly, child_poly):
    """
    Merge child_poly (hole) into parent_poly using a cut line (keyhole).
    """
    if not parent_poly or not child_poly:
        return parent_poly
        
    idx_p, idx_c = find_closest_points(parent_poly, child_poly)
    
    # Construct merged polygon
    # Sequence: Parent(start..idx_p) -> Child(idx_c..end) -> Child(start..idx_c) -> Parent(idx_p..end)
    # Note: We duplicate the connecting points to close the loop properly
    
    new_poly = []
    
    # 1. Parent up to cut point
    new_poly.extend(parent_poly[:idx_p+1])
    
    # 2. Cut line to Child
    # We add child points starting from closest point, going around, and back to closest
    child_rotated = child_poly[idx_c:] + child_poly[:idx_c]
    child_rotated.append(child_poly[idx_c]) # Close the child loop back to start of cut
    new_poly.extend(child_rotated)
    
    # 3. Return to Parent cut point
    new_poly.append(parent_poly[idx_p])
    
    # 4. Rest of Parent
    new_poly.extend(parent_poly[idx_p+1:])
    
    return new_poly

def mask_to_labelme(mask_dir, output_dir, img_dir, label_name='road', callback=None):
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    mask_files = glob.glob(os.path.join(mask_dir, '*.png'))
    total_files = len(mask_files)
    
    msg = f"Found {total_files} masks in {mask_dir}"
    print(msg)
    if callback:
        callback(msg)

    for i, mask_path in enumerate(mask_files):
        basename = os.path.basename(mask_path)
        filename_no_ext = os.path.splitext(basename)[0]
        image_filename = filename_no_ext + ".jpg"
        
        # Report progress
        if callback and i % 10 == 0:
            callback(f"Processing {i+1}/{total_files}: {basename}")
        
        mask = cv2.imread(mask_path, cv2.IMREAD_GRAYSCALE)
        if mask is None:
            err_msg = f"Error reading {mask_path}"
            print(err_msg)
            if callback:
                callback(f"Error: {err_msg}")
            continue
            
        h, w = mask.shape
        
        # Use RETR_TREE to get hierarchy
        contours, hierarchy = cv2.findContours(mask, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)
        
        final_shapes = []
        
        if hierarchy is not None:
            hierarchy = hierarchy[0]
            
            # 1. Collect all contours and simplify them
            processed_contours = {} # index -> points
            for i, contour in enumerate(contours):
                if cv2.contourArea(contour) < 20:
                    continue
                # Simplify contour slightly to reduce point count
                # Epsilon controls the approximation accuracy. 
                # Smaller value = more points = closer to original shape.
                # Previously 0.001 * arcLength, try smaller or remove approximation if shape distortion is too high.
                # Let's try 0.0005 or even skip it if we rely on simplify_points later.
                # However, approxPolyDP is good for noise. Let's make it very conservative.
                # epsilon = 0.0005 * cv2.arcLength(contour, True)
                # approx = cv2.approxPolyDP(contour, epsilon, True)
                # points = approx.reshape(-1, 2).tolist()
                
                # Use raw contour points directly
                points = contour.reshape(-1, 2).tolist()
                if len(points) < 3:
                    continue
                processed_contours[i] = points

            # 2. Identify Parents and Children
            # We map each contour to its parent index.
            # If parent is -1, it's a top-level contour (Road).
            # If parent is not -1, check parent's parent...
            # Actually, standard RETR_TREE: 
            # Depth 0 (Ext): Road
            # Depth 1 (Hole): Background -> Needs to be merged into Depth 0
            # Depth 2 (Island inside Hole): Road -> Separate shape
            
            # Group by "Ultimate Positive Parent"
            # We want to merge Depth 1 holes into Depth 0 parents.
            # We want to leave Depth 2 islands as new independent parents.
            
            # Strategy:
            # - Identify "Positive" contours (Depth 0, 2, 4...)
            # - Identify "Negative" contours (Depth 1, 3, 5...)
            # - Assign each Negative contour to its direct Parent (which must be Positive).
            
            positive_polys = {} # index -> list of points
            holes_map = {} # parent_index -> list of hole indices
            
            for i in processed_contours:
                # Calculate depth
                depth = 0
                p_idx = hierarchy[i][3]
                while p_idx != -1:
                    depth += 1
                    p_idx = hierarchy[p_idx][3]
                
                if depth % 2 == 0:
                    # Positive (Road)
                    positive_polys[i] = processed_contours[i]
                else:
                    # Negative (Hole)
                    parent = hierarchy[i][3]
                    if parent != -1 and parent in processed_contours: # Ensure parent is valid/large enough
                        if parent not in holes_map:
                            holes_map[parent] = []
                        holes_map[parent].append(i)
            
            # 3. Merge Holes into Parents
            for parent_idx, parent_poly in positive_polys.items():
                merged_poly = parent_poly
                if parent_idx in holes_map:
                    for hole_idx in holes_map[parent_idx]:
                        hole_poly = processed_contours[hole_idx]
                        merged_poly = merge_polygons(merged_poly, hole_poly)
                
                # Simplify points to reduce density
                # Adjust min_dist as needed. 5.0 pixels is usually a good balance.
                # User reported sharp artifacts, suggesting aggressive simplification removed critical corners.
                # Reducing min_dist back to a safer value (e.g. 5.0 or 10.0) to preserve shape fidelity.
                # final_poly = simplify_points(merged_poly, min_dist=10.0)
                
                # No simplification as requested by user
                final_poly = merged_poly
                
                if len(final_poly) < 3:
                    continue

                shape = {
                    "label": label_name,
                    "points": final_poly,
                    "group_id": None,
                    "shape_type": "polygon",
                    "flags": {}
                }
                final_shapes.append(shape)
            
        # Create JSON structure
        data = {
            "version": "5.0.1",
            "flags": {},
            "shapes": final_shapes,
            "imagePath": os.path.join("..", "testimgs", image_filename),
            "imageData": None,
            "imageHeight": h,
            "imageWidth": w
        }
        
        output_path = os.path.join(output_dir, filename_no_ext + ".json")
        with open(output_path, 'w') as f:
            json.dump(data, f, indent=2)
            
    print(f"Conversion completed. Results saved in {output_dir}")

if __name__ == "__main__":
    mask_dir = "testmasks"
    img_dir = "testimgs" 
    output_dir = "testlabelmemask"
    
    mask_to_labelme(mask_dir, output_dir, img_dir)
