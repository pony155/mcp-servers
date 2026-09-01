operations.compare_frames = function(input)
  local sprite = open_sprite(input.source_path)
  local first = render_frame_image(sprite, input.first_frame + 1)
  local second = render_frame_image(sprite, input.second_frame + 1)
  if sprite.width * sprite.height > input.max_pixel_visits then
    sprite:close()
    fail("LIMIT_EXCEEDED", "frame comparison exceeds the pixel visit limit")
  end
  local changed = 0
  local min_x, min_y, max_x, max_y = sprite.width, sprite.height, -1, -1
  local first_baseline, second_baseline = nil, nil
  local difference = nil
  if input.difference_output_path ~= nil then
    difference = Image(sprite.width, sprite.height, ColorMode.RGB)
    difference:clear()
  end
  for y = 0, sprite.height - 1 do
    for x = 0, sprite.width - 1 do
      local first_pixel = first:getPixel(x, y)
      local second_pixel = second:getPixel(x, y)
      local _, _, _, first_alpha = pixel_rgba(sprite, nil, first_pixel)
      local _, _, _, second_alpha = pixel_rgba(sprite, nil, second_pixel)
      if first_alpha > 0 then first_baseline = y end
      if second_alpha > 0 then second_baseline = y end
      if first_pixel ~= second_pixel then
        changed = changed + 1
        min_x, min_y = math.min(min_x, x), math.min(min_y, y)
        max_x, max_y = math.max(max_x, x), math.max(max_y, y)
        if difference ~= nil then
          difference:drawPixel(x, y, app.pixelColor.rgba(255, 0, 255, 255))
        end
      end
    end
  end
  if difference ~= nil then difference:saveAs(input.difference_output_path) end
  local bounds = nil
  if changed > 0 then
    bounds = { x = min_x, y = min_y, width = max_x - min_x + 1, height = max_y - min_y + 1 }
  end
  local baseline_delta = nil
  if first_baseline ~= nil and second_baseline ~= nil then
    baseline_delta = second_baseline - first_baseline
  end
  local result = {
    first_frame = input.first_frame,
    second_frame = input.second_frame,
    changed_pixel_count = changed,
    changed_bounds = bounds,
    first_baseline = first_baseline,
    second_baseline = second_baseline,
    baseline_delta = baseline_delta
  }
  sprite:close()
  return result
end

operations.inspect_cels = function(input)
  local sprite = open_sprite(input.source_path)
  local groups, next_group, cels = {}, 1, {}
  for _, cel in ipairs(sprite.cels) do
    local image_id = cel.image.id
    if groups[image_id] == nil then groups[image_id], next_group = next_group, next_group + 1 end
    local layer_path = cel.layer.name
    local parent = cel.layer.parent
    while parent ~= nil and parent.name ~= nil do
      layer_path = parent.name .. "/" .. layer_path
      parent = parent.parent
    end
    table.insert(cels, { layer = layer_path, frame = cel.frame.frameNumber - 1,
      position = point_info(cel.position), bounds = rectangle_info(cel.bounds),
      opacity = cel.opacity, z_index = cel.zIndex, image_id = image_id,
      linked_group = groups[image_id] })
  end
  sprite:close()
  return { cels = cels }
end

local function layer_signature(sprite)
  local values = {}
  local function walk(layers, prefix)
    for _, layer in ipairs(layers) do
      local path = prefix == "" and layer.name or prefix .. "/" .. layer.name
      local kind = layer.isGroup and "group" or (layer.isTilemap and "tilemap" or
        (layer.isBackground and "background" or "image"))
      table.insert(values, path .. ":" .. kind)
      if layer.isGroup then walk(layer.layers, path) end
    end
  end
  walk(sprite.layers, "")
  return table.concat(values, "|")
end

local function tag_signature(sprite)
  local values = {}
  for _, tag in ipairs(sprite.tags) do
    table.insert(values, tag.name .. ":" .. tag.fromFrame.frameNumber .. ":" ..
      tag.toFrame.frameNumber .. ":" .. animation_direction_name(tag.aniDir) .. ":" ..
      tostring(tag.repeats or 0))
  end
  return table.concat(values, "|")
end

local function palette_signature(sprite)
  local values = {}
  for _, palette in ipairs(sprite.palettes) do
    local frame = 1
    if type(palette.frame) == "number" then frame = palette.frame
    elseif palette.frame ~= nil then frame = palette.frame.frameNumber end
    table.insert(values, "frame=" .. frame .. ":size=" .. #palette)
    for index = 0, #palette - 1 do
      local color = palette:getColor(index)
      table.insert(values, rgba_hex(color.red, color.green, color.blue, color.alpha))
    end
  end
  return table.concat(values, "|")
end

local function slice_signature(sprite)
  local values = {}
  for _, slice in ipairs(sprite.slices) do
    local bounds = slice.bounds
    local value = slice.name .. ":" .. bounds.x .. ":" .. bounds.y .. ":" ..
      bounds.width .. ":" .. bounds.height
    if slice.center ~= nil then
      local center = slice.center
      value = value .. ":c=" .. center.x .. "," .. center.y .. "," ..
        center.width .. "," .. center.height
    end
    if slice.pivot ~= nil then
      value = value .. ":p=" .. slice.pivot.x .. "," .. slice.pivot.y
    end
    table.insert(values, value)
  end
  return table.concat(values, "|")
end

operations.compare_sprites = function(input)
  local first = open_sprite(input.first_source_path)
  local second = open_sprite(input.second_source_path)
  local same_dimensions = first.width == second.width and first.height == second.height
  local same_frame_count = #first.frames == #second.frames
  local same_color_mode = first.colorMode == second.colorMode
  local changed_frames, total_changed, visits = {}, 0, 0
  local width, height = math.max(first.width, second.width), math.max(first.height, second.height)
  local frame_count = math.max(#first.frames, #second.frames)
  for frame = 1, frame_count do
    local first_image = frame <= #first.frames and render_frame_image(first, frame) or nil
    local second_image = frame <= #second.frames and render_frame_image(second, frame) or nil
    local changed, left, top, right, bottom = 0, nil, nil, nil, nil
    for y = 0, height - 1 do for x = 0, width - 1 do
      visits = visits + 1
      if visits > input.max_pixel_visits then fail("LIMIT_EXCEEDED", "sprite comparison exceeds pixel visit limit") end
      local ar, ag, ab, aa = 0, 0, 0, 0
      local br, bg, bb, ba = 0, 0, 0, 0
      if first_image ~= nil and x < first.width and y < first.height then
        ar, ag, ab, aa = pixel_rgba(first, nil, first_image:getPixel(x, y))
      end
      if second_image ~= nil and x < second.width and y < second.height then
        br, bg, bb, ba = pixel_rgba(second, nil, second_image:getPixel(x, y))
      end
      if ar ~= br or ag ~= bg or ab ~= bb or aa ~= ba then
        changed = changed + 1
        left = left == nil and x or math.min(left, x); top = top == nil and y or math.min(top, y)
        right = right == nil and x or math.max(right, x); bottom = bottom == nil and y or math.max(bottom, y)
      end
    end end
    if changed > 0 then
      table.insert(changed_frames, {frame=frame-1, changed_pixel_count=changed,
        changed_bounds={x=left,y=top,width=right-left+1,height=bottom-top+1}})
      total_changed = total_changed + changed
    end
  end
  local same_layers = layer_signature(first) == layer_signature(second)
  local same_tags = tag_signature(first) == tag_signature(second)
  local same_slices = slice_signature(first) == slice_signature(second)
  local same_palette = palette_signature(first) == palette_signature(second)
  first:close(); second:close()
  return {identical=same_dimensions and same_frame_count and same_color_mode and same_layers and
      same_palette and same_tags and same_slices and total_changed==0,
    same_dimensions=same_dimensions, same_frame_count=same_frame_count,
    same_color_mode=same_color_mode, same_palette=same_palette, same_layer_structure=same_layers,
    same_tags=same_tags, same_slices=same_slices,
    changed_pixel_count=total_changed, changed_frames=changed_frames}
end

operations.generate_collision_masks = function(input)
  local sprite = open_sprite(input.source_path)
  local selected = input.frames or {}
  if #selected == 0 then for index = 0, #sprite.frames - 1 do table.insert(selected, index) end end
  local layer = nil
  if input.layer ~= nil then
    layer = find_layer(sprite, input.layer)
    if layer.isGroup or layer.isTilemap then fail("INVALID_SELECTOR", "collision layer must be an image layer") end
  end
  local results, visits = {}, 0
  for _, zero_frame in ipairs(selected) do
    local frame = zero_frame + 1
    if frame < 1 or frame > #sprite.frames then fail("INVALID_SELECTOR", "collision frame is outside the sprite") end
    local image
    if layer == nil then image = render_frame_image(sprite, frame)
    else
      image = Image(sprite.spec); image:clear(); local cel = layer:cel(frame)
      if cel ~= nil then image:drawImage(cel.image, cel.position) end
    end
    local solid = {}
    for y = 0, sprite.height - 1 do for x = 0, sprite.width - 1 do
      visits = visits + 1
      if visits > input.max_pixel_visits then fail("LIMIT_EXCEEDED", "collision scan exceeds pixel visit limit") end
      local _, _, _, alpha = pixel_rgba(sprite, layer, image:getPixel(x, y))
      if alpha >= input.alpha_threshold then solid[y * sprite.width + x] = true end
    end end
    local rectangles = {}
    if input.mode == "bounds" then
      local left, top, right, bottom = nil, nil, nil, nil
      for key in pairs(solid) do local x, y = key % sprite.width, math.floor(key / sprite.width)
        left=left==nil and x or math.min(left,x);top=top==nil and y or math.min(top,y)
        right=right==nil and x or math.max(right,x);bottom=bottom==nil and y or math.max(bottom,y) end
      if left ~= nil then table.insert(rectangles,{x=left,y=top,width=right-left+1,height=bottom-top+1}) end
    else
      local visited = {}
      for key in pairs(solid) do if not visited[key] then
        local queue, head = {key}, 1; visited[key] = true
        local left, top, right, bottom = nil, nil, nil, nil
        while head <= #queue do local current=queue[head];head=head+1
          local x,y=current%sprite.width,math.floor(current/sprite.width)
          left=left==nil and x or math.min(left,x);top=top==nil and y or math.min(top,y)
          right=right==nil and x or math.max(right,x);bottom=bottom==nil and y or math.max(bottom,y)
          local neighbors={current-1,current+1,current-sprite.width,current+sprite.width}
          for index,neighbor in ipairs(neighbors) do
            local valid=(index~=1 or x>0) and (index~=2 or x<sprite.width-1) and
              (index~=3 or y>0) and (index~=4 or y<sprite.height-1)
            if valid and solid[neighbor] and not visited[neighbor] then visited[neighbor]=true;table.insert(queue,neighbor) end
          end
        end
        table.insert(rectangles,{x=left,y=top,width=right-left+1,height=bottom-top+1})
        if #rectangles > input.max_components then fail("LIMIT_EXCEEDED", "collision component count exceeds limit") end
      end end
    end
    table.insert(results, {frame=zero_frame, rectangles=rectangles})
  end
  sprite:close()
  return {frames=results}
end

operations.validate_pixel_art = function(input)
  local sprite = open_sprite(input.source_path)
  local frames = input.frames or {}
  if #frames == 0 then for index = 0, #sprite.frames - 1 do table.insert(frames, index) end end
  local allowed = {}
  for _, color in ipairs(input.allowed_palette or {}) do
    local parsed = parse_color(color)
    allowed[rgba_hex(parsed.red, parsed.green, parsed.blue, parsed.alpha)] = true
  end
  local colors, semi, off_palette, isolated, visits = {}, 0, 0, 0, 0
  local first_semi, first_off, first_isolated = nil, nil, nil
  for _, zero_frame in ipairs(frames) do
    local frame = zero_frame + 1
    if frame < 1 or frame > #sprite.frames then fail("INVALID_SELECTOR", "validation frame is outside the sprite") end
    local image = render_frame_image(sprite, frame)
    local opaque = {}
    for y = 0, sprite.height - 1 do for x = 0, sprite.width - 1 do
      visits = visits + 1
      if visits > input.max_pixel_visits then fail("LIMIT_EXCEEDED", "pixel-art validation exceeds pixel limit") end
      local red, green, blue, alpha = pixel_rgba(sprite, nil, image:getPixel(x, y))
      if alpha > 0 then
        local hex = rgba_hex(red, green, blue, alpha); colors[hex] = true
        opaque[y * sprite.width + x] = true
        if alpha < 255 then semi = semi + 1; first_semi = first_semi or {frame=zero_frame,x=x,y=y} end
        if next(allowed) ~= nil and not allowed[hex] then
          off_palette = off_palette + 1; first_off = first_off or {frame=zero_frame,x=x,y=y}
        end
      end
    end end
    if input.detect_isolated_pixels then
      for key in pairs(opaque) do
        local x, y = key % sprite.width, math.floor(key / sprite.width)
        local connected = (x > 0 and opaque[key - 1]) or
          (x < sprite.width - 1 and opaque[key + 1]) or
          (y > 0 and opaque[key - sprite.width]) or
          (y < sprite.height - 1 and opaque[key + sprite.width])
        if not connected then
          isolated = isolated + 1
          first_isolated = first_isolated or {frame=zero_frame,x=x,y=y}
        end
      end
    end
  end
  local unique = 0; for _ in pairs(colors) do unique = unique + 1 end
  local issues = {}
  if input.max_colors ~= nil and unique > input.max_colors then
    table.insert(issues, {code="TOO_MANY_COLORS",severity="error",
      message="Opaque unique color count exceeds max_colors"})
  end
  if input.require_binary_alpha and semi > 0 then
    table.insert(issues, {code="SEMI_TRANSPARENT_PIXELS",severity="error",
      message="Sprite contains partially transparent pixels",frame=first_semi.frame,
      x=first_semi.x,y=first_semi.y})
  end
  if off_palette > 0 then
    table.insert(issues, {code="OFF_PALETTE_PIXELS",severity="error",
      message="Sprite contains colors outside allowed_palette",frame=first_off.frame,
      x=first_off.x,y=first_off.y})
  end
  if isolated > 0 then
    table.insert(issues, {code="ISOLATED_PIXELS",severity="warning",
      message="Sprite contains opaque pixels without orthogonal neighbors",
      frame=first_isolated.frame,x=first_isolated.x,y=first_isolated.y})
  end
  local valid = true; for _, issue in ipairs(issues) do if issue.severity == "error" then valid = false end end
  sprite:close()
  return {valid=valid,frames=frames,unique_colors=unique,semi_transparent_pixels=semi,
    off_palette_pixels=off_palette,isolated_pixels=isolated,issues=issues}
end

operations.validate_loop_transition = function(input)
  local sprite = open_sprite(input.source_path)
  local first, last = input.first_frame, input.last_frame
  if input.tag ~= nil then
    local tag = find_tag(sprite, input.tag)
    if tag == nil then fail("INVALID_SELECTOR", "animation tag was not found") end
    first, last = tag.fromFrame.frameNumber - 1, tag.toFrame.frameNumber - 1
  elseif last == nil then last = #sprite.frames - 1 end
  if first < 0 or last < 0 or first >= #sprite.frames or last >= #sprite.frames or first > last then
    fail("INVALID_SELECTOR", "loop frame range is outside or out of order")
  end
  if sprite.width * sprite.height > input.max_pixel_visits then
    fail("LIMIT_EXCEEDED", "loop validation exceeds the pixel visit limit")
  end
  local first_image, last_image = render_frame_image(sprite, first + 1), render_frame_image(sprite, last + 1)
  local changed, left, top, right, bottom = 0, nil, nil, nil, nil
  for y = 0, sprite.height - 1 do for x = 0, sprite.width - 1 do
    local ar, ag, ab, aa = pixel_rgba(sprite, nil, first_image:getPixel(x, y))
    local br, bg, bb, ba = pixel_rgba(sprite, nil, last_image:getPixel(x, y))
    if ar ~= br or ag ~= bg or ab ~= bb or aa ~= ba then
      changed = changed + 1
      left=left==nil and x or math.min(left,x);top=top==nil and y or math.min(top,y)
      right=right==nil and x or math.max(right,x);bottom=bottom==nil and y or math.max(bottom,y)
    end
  end end
  local first_duration = math.floor(sprite.frames[first + 1].duration * 1000 + 0.5)
  local last_duration = math.floor(sprite.frames[last + 1].duration * 1000 + 0.5)
  local duration_delta = last_duration - first_duration
  local issues = {}
  if changed > input.max_changed_pixels then
    table.insert(issues,{code="LOOP_PIXEL_DISCONTINUITY",severity="error",
      message="Loop endpoints exceed the allowed changed-pixel count",frames={first,last}})
  end
  if input.require_equal_duration and duration_delta ~= 0 then
    table.insert(issues,{code="LOOP_DURATION_MISMATCH",severity="error",
      message="Loop endpoint durations differ",frames={first,last}})
  end
  local bounds = nil
  if left ~= nil then bounds={x=left,y=top,width=right-left+1,height=bottom-top+1} end
  local changed_ratio = changed / (sprite.width * sprite.height)
  sprite:close()
  return {valid=#issues==0,tag=input.tag,first_frame=first,last_frame=last,
    changed_pixel_count=changed,changed_ratio=changed_ratio,
    changed_bounds=bounds,first_duration_ms=first_duration,last_duration_ms=last_duration,
    duration_delta_ms=duration_delta,issues=issues}
end

local function motion_image(sprite, layer, frame)
  if layer == nil then return render_frame_image(sprite, frame) end
  local image = Image(sprite.spec); image:clear(); local cel = layer:cel(frame)
  if cel ~= nil then image:drawImage(cel.image, cel.position, cel.opacity) end
  return image
end

operations.generate_motion_report = function(input)
  local sprite = open_sprite(input.source_path)
  local layer = nil
  if input.layer ~= nil then
    layer = find_layer(sprite, input.layer)
    if layer.isGroup or layer.isTilemap then fail("INVALID_SELECTOR", "motion report requires an image layer") end
  end
  local first, last = 1, #sprite.frames
  if input.tag ~= nil then
    local tag = find_tag(sprite, input.tag)
    if tag == nil then fail("INVALID_SELECTOR", "animation tag was not found") end
    first, last = tag.fromFrame.frameNumber, tag.toFrame.frameNumber
  end
  if sprite.width * sprite.height * (last - first + 1) > input.max_pixel_visits then
    fail("LIMIT_EXCEEDED", "motion report exceeds pixel visit limit")
  end
  local metrics, total_distance, maximum_speed = {}, 0, 0
  local previous_centroid, previous_velocity, previous_duration = nil, nil, nil
  for frame = first, last do
    local image = motion_image(sprite, layer, frame)
    local left, top, right, bottom, count, sum_x, sum_y = nil, nil, nil, nil, 0, 0, 0
    for y = 0, sprite.height - 1 do for x = 0, sprite.width - 1 do
      local _, _, _, alpha = pixel_rgba(sprite, nil, image:getPixel(x, y))
      if alpha >= input.alpha_threshold then
        count, sum_x, sum_y = count + 1, sum_x + x, sum_y + y
        left=left==nil and x or math.min(left,x);top=top==nil and y or math.min(top,y)
        right=right==nil and x or math.max(right,x);bottom=bottom==nil and y or math.max(bottom,y)
      end
    end end
    local centroid, velocity_x, velocity_y, acceleration_x, acceleration_y = nil, nil, nil, nil, nil
    if count > 0 then centroid = {x=sum_x/count, y=sum_y/count} end
    if centroid ~= nil and previous_centroid ~= nil then
      local seconds = previous_duration / 1000
      velocity_x = (centroid.x - previous_centroid.x) / seconds
      velocity_y = (centroid.y - previous_centroid.y) / seconds
      local speed = math.sqrt(velocity_x*velocity_x + velocity_y*velocity_y)
      total_distance = total_distance + math.sqrt(
        (centroid.x-previous_centroid.x)^2 + (centroid.y-previous_centroid.y)^2)
      maximum_speed = math.max(maximum_speed, speed)
      if previous_velocity ~= nil then
        acceleration_x = (velocity_x - previous_velocity.x) / seconds
        acceleration_y = (velocity_y - previous_velocity.y) / seconds
      end
      previous_velocity = {x=velocity_x,y=velocity_y}
    else previous_velocity = nil end
    local duration = math.floor(sprite.frames[frame].duration * 1000 + 0.5)
    table.insert(metrics,{frame=frame-1,duration_ms=duration,
      bounds=left and {x=left,y=top,width=right-left+1,height=bottom-top+1} or nil,
      opaque_pixels=count,centroid=centroid,velocity_x=velocity_x,velocity_y=velocity_y,
      acceleration_x=acceleration_x,acceleration_y=acceleration_y})
    previous_centroid, previous_duration = centroid, duration
  end
  sprite:close()
  return {tag=input.tag,layer=input.layer,frames=metrics,total_distance=total_distance,
    maximum_speed=maximum_speed}
end

local function collision_source_image(sprite, layer, frame)
  if layer == nil then return render_frame_image(sprite, frame) end
  local image = Image(sprite.spec); image:clear(); local cel = layer:cel(frame)
  if cel ~= nil then image:drawImage(cel.image, cel.position, cel.opacity) end
  return image
end

local function polygon_area(points)
  local area = 0
  for index = 1, #points do
    local next_index = index % #points + 1
    area = area + points[index].x * points[next_index].y -
      points[next_index].x * points[index].y
  end
  return area / 2
end

local function simplify_polygon(points, tolerance)
  local changed = true
  while changed and #points > 3 do
    changed = false
    for index = #points, 1, -1 do
      local previous = points[(index - 2) % #points + 1]
      local current = points[index]
      local following = points[index % #points + 1]
      local dx, dy = following.x - previous.x, following.y - previous.y
      local length = math.sqrt(dx*dx + dy*dy)
      local distance = length == 0 and 0 or
        math.abs(dy*current.x - dx*current.y + following.x*previous.y -
          following.y*previous.x) / length
      if #points > 3 and distance <= tolerance then table.remove(points,index);changed=true end
    end
  end
  return points
end

local function normalize_polygon(points)
  if polygon_area(points) < 0 then
    local reversed = {}
    for index = #points, 1, -1 do table.insert(reversed, points[index]) end
    points = reversed
  end
  local start = 1
  for index = 2, #points do
    if points[index].y < points[start].y or
      (points[index].y == points[start].y and points[index].x < points[start].x) then
      start = index
    end
  end
  local normalized = {}
  for offset = 0, #points - 1 do
    table.insert(normalized, points[(start + offset - 1) % #points + 1])
  end
  return normalized
end

local function trace_component(component, width, tolerance)
  local outgoing = {}
  local function add_edge(ax,ay,bx,by)
    local key=ax..","..ay;outgoing[key]=outgoing[key] or {}
    table.insert(outgoing[key],{x=bx,y=by})
  end
  for key in pairs(component) do
    local x,y=key%width,math.floor(key/width)
    if not component[key-width] then add_edge(x,y,x+1,y) end
    if not component[key+1] or x==width-1 then add_edge(x+1,y,x+1,y+1) end
    if not component[key+width] then add_edge(x+1,y+1,x,y+1) end
    if not component[key-1] or x==0 then add_edge(x,y+1,x,y) end
  end
  local loops = {}
  while true do
    local start_key,start_edges=nil,nil
    for key,edges in pairs(outgoing) do if #edges>0 then start_key,start_edges=key,edges;break end end
    if start_key==nil then break end
    local comma=string.find(start_key,",");local sx=tonumber(string.sub(start_key,1,comma-1))
    local sy=tonumber(string.sub(start_key,comma+1));local x,y=sx,sy;local points={}
    repeat
      table.insert(points,{x=x,y=y});local key=x..","..y;local edges=outgoing[key]
      if edges==nil or #edges==0 then fail("ASEPRITE_FAILED","collision contour is open") end
      local target=table.remove(edges);x,y=target.x,target.y
    until x==sx and y==sy
    table.insert(loops,normalize_polygon(simplify_polygon(points,tolerance)))
  end
  local largest,largest_area=nil,0
  for _,points in ipairs(loops) do local area=math.abs(polygon_area(points))
    if area>largest_area then largest,largest_area=points,area end end
  return largest,largest_area
end

operations.generate_collision_polygons = function(input)
  local sprite=open_sprite(input.source_path);local layer=nil
  if input.layer~=nil then layer=find_layer(sprite,input.layer)
    if layer.isGroup or layer.isTilemap then fail("INVALID_SELECTOR","collision polygons require an image layer") end end
  local frames=input.frames or {};if #frames==0 then for index=0,#sprite.frames-1 do table.insert(frames,index) end end
  local results,visits,polygon_count={},0,0
  for _,zero_frame in ipairs(frames) do
    local frame=zero_frame+1;if frame<1 or frame>#sprite.frames then fail("INVALID_SELECTOR","collision frame is outside sprite") end
    local image=collision_source_image(sprite,layer,frame);local solid={}
    for y=0,sprite.height-1 do for x=0,sprite.width-1 do visits=visits+1
      if visits>input.max_pixel_visits then fail("LIMIT_EXCEEDED","collision polygon scan exceeds pixel limit") end
      local _,_,_,alpha=pixel_rgba(sprite,nil,image:getPixel(x,y));if alpha>=input.alpha_threshold then solid[y*sprite.width+x]=true end
    end end
    local visited,polygons={},{}
    for key in pairs(solid) do if not visited[key] then
      local queue,head,component={key},1,{};visited[key]=true
      while head<=#queue do local current=queue[head];head=head+1;component[current]=true
        local x,y=current%sprite.width,math.floor(current/sprite.width)
        local neighbors={current-1,current+1,current-sprite.width,current+sprite.width}
        for index,neighbor in ipairs(neighbors) do local valid=(index~=1 or x>0) and
          (index~=2 or x<sprite.width-1) and (index~=3 or y>0) and (index~=4 or y<sprite.height-1)
          if valid and solid[neighbor] and not visited[neighbor] then visited[neighbor]=true;table.insert(queue,neighbor) end end
      end
      local points,area=trace_component(component,sprite.width,input.simplify_tolerance)
      if points~=nil then polygon_count=polygon_count+1
        if polygon_count>input.max_polygons then fail("LIMIT_EXCEEDED","collision polygon count exceeds limit") end
        if #points>input.max_points_per_polygon then fail("LIMIT_EXCEEDED","collision polygon point count exceeds limit") end
        table.insert(polygons,{points=points,area=area}) end
    end end
    table.sort(polygons,function(a,b)
      if a.points[1].y~=b.points[1].y then return a.points[1].y<b.points[1].y end
      if a.points[1].x~=b.points[1].x then return a.points[1].x<b.points[1].x end
      return a.area>b.area
    end)
    table.insert(results,{frame=zero_frame,polygons=polygons})
  end
  sprite:close();return {frames=results}
end

operations.validate_animation = function(input)
  local sprite = open_sprite(input.source_path)
  local result = validate_animation(sprite, input)
  sprite:close()
  return result
end
