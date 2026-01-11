import json
import os
import glob
import numpy as np
import cv2
import PIL.Image
# import labelme.utils # Not strictly needed if we implement logic manually

def json_to_mask(json_dir, output_dir, label_name='road', callback=None):
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    json_files = glob.glob(os.path.join(json_dir, '*.json'))
    total_files = len(json_files)
    msg = f"Found {total_files} json files in {json_dir}"
    print(msg)
    if callback:
        callback(msg)

    for i, json_path in enumerate(json_files):
        filename = os.path.basename(json_path)
        filename_no_ext = os.path.splitext(filename)[0]
        
        # Report progress
        if callback and i % 10 == 0:
            callback(f"Processing {i+1}/{total_files}: {filename}")
        
        with open(json_path, 'r') as f:
            data = json.load(f)

        img_h = data.get('imageHeight')
        img_w = data.get('imageWidth')
        
        # If height/width not in JSON, try to read from imagePath (optional, usually they are in JSON)
        if img_h is None or img_w is None:
            err_msg = f"Warning: Image size not found in {json_path}, skipping."
            print(err_msg)
            if callback:
                callback(err_msg)
            continue

        # Create empty mask (0 = background)
        # Using uint8: 0 for background, 255 for road
        mask = np.zeros((img_h, img_w), dtype=np.uint8)
        
        shapes = data.get('shapes', [])
        
        # We need to handle polygons.
        # Since we merged holes using the keyhole method, the polygon is complex but valid.
        # cv2.fillPoly handles complex polygons correctly (even self-intersecting ones usually, 
        # but keyhole polygons are not self-intersecting, just touching).
        # Even-Odd rule is typically used for filling, but cv2.fillPoly simply fills the area bounded by the contour.
        # For a keyhole polygon, it will fill the "road" part and leave the "hole" part empty because the path goes around it.
        
        for shape in shapes:
            label = shape.get('label')
            points = shape.get('points')
            
            if label == label_name:
                # Convert points to integer numpy array
                pts = np.array(points, dtype=np.int32)
                pts = pts.reshape((-1, 1, 2))
                
                # Fill the polygon with white (255)
                # cv2.fillPoly fills the area inside the contour.
                # Since our "hole" is technically "outside" the contour due to the keyhole cut, 
                # it should remain black (0).
                cv2.fillPoly(mask, [pts], color=255)
                
        # Save mask
        output_path = os.path.join(output_dir, filename_no_ext + ".png")
        cv2.imwrite(output_path, mask)
        
    print(f"Conversion completed. Masks saved in {output_dir}")

if __name__ == "__main__":
    # Adjust these paths as needed
    json_dir = "testsave" 
    output_dir = "final_masks"
    
    json_to_mask(json_dir, output_dir)
