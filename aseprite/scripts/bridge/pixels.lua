operations.set_pixels = function(input)
  local sprite = open_sprite(input.source_path)
  local layer = find_layer(sprite, input.layer)
  app.transaction("MCP set pixels", function()
    draw_pixels(sprite, layer, input.frame + 1, input.pixels)
  end)
  local saved = sprite:saveCopyAs(input.output_path)
  if saved == false then fail("ASEPRITE_FAILED", "Aseprite could not save the edited document") end
  local result = inspect_sprite(sprite, false, input.output_path)
  sprite:close()
  return result
end

operations.read_pixels = function(input)
  local sprite = open_sprite(input.source_path)
  local layer = find_layer(sprite, input.layer)
  if layer.isGroup or layer.isTilemap then
    sprite:close()
    fail("INVALID_SELECTOR", "pixels can only be read from an image layer")
  end
  local frame_number = input.frame + 1
  if frame_number < 1 or frame_number > #sprite.frames then
    sprite:close()
    fail("INVALID_SELECTOR", "frame index is outside the sprite")
  end
  if input.x + input.width > sprite.width or input.y + input.height > sprite.height then
    sprite:close()
    fail("INVALID_SELECTOR", "pixel bounds extend outside the sprite")
  end
  local cel = layer:cel(frame_number)
  local runs = {}
  local pixel_count = 0
  for y = input.y, input.y + input.height - 1 do
    local run_color, run_x, run_length = nil, nil, 0
    for x = input.x, input.x + input.width - 1 do
      local red, green, blue, alpha = 0, 0, 0, 0
      if cel ~= nil then
        local image_x = x - cel.position.x
        local image_y = y - cel.position.y
        if image_x >= 0 and image_x < cel.image.width and image_y >= 0 and image_y < cel.image.height then
          red, green, blue, alpha = pixel_rgba(sprite, layer, cel.image:getPixel(image_x, image_y))
        end
      end
      local color = rgba_hex(red, green, blue, alpha)
      local included = input.include_transparent == true or alpha > 0
      if included then
        pixel_count = pixel_count + 1
        if run_color == color and run_x + run_length == x then
          run_length = run_length + 1
        else
          if run_color ~= nil then
            table.insert(runs, { x = run_x, y = y, length = run_length, color = run_color })
          end
          run_color, run_x, run_length = color, x, 1
        end
      else
        if run_color ~= nil then
          table.insert(runs, { x = run_x, y = y, length = run_length, color = run_color })
          run_color, run_x, run_length = nil, nil, 0
        end
      end
    end
    if run_color ~= nil then
      table.insert(runs, { x = run_x, y = y, length = run_length, color = run_color })
    end
  end
  local result = {
    layer = input.layer,
    frame = input.frame,
    bounds = { x = input.x, y = input.y, width = input.width, height = input.height },
    encoding = "rgba_runs",
    runs = runs,
    pixel_count = pixel_count
  }
  sprite:close()
  return result
end

operations.transform_cel = function(input)
  local sprite = open_sprite(input.source_path)
  local layer = find_layer(sprite, input.layer)
  if layer.isGroup or layer.isTilemap then
    sprite:close()
    fail("INVALID_SELECTOR", "cel transforms require an image layer")
  end
  local frame_number = input.frame + 1
  if frame_number < 1 or frame_number > #sprite.frames then
    sprite:close()
    fail("INVALID_SELECTOR", "frame index is outside the sprite")
  end
  local cel = layer:cel(frame_number)
  if cel == nil then
    sprite:close()
    fail("INVALID_SELECTOR", "the selected layer and frame do not contain a cel")
  end
  app.transaction("MCP transform cel", function()
    if input.action == "translate" then
      cel.position = Point(cel.position.x + input.offset_x, cel.position.y + input.offset_y)
    elseif input.action == "flip_horizontal" or input.action == "flip_vertical" or
      input.action == "rotate_90_cw" or input.action == "rotate_90_ccw" then
      cel.image = transformed_image(sprite, cel.image, input.action)
    else
      fail("INVALID_INPUT", "unsupported cel transform action")
    end
  end)
  save_copy(sprite, input.output_path)
  local result = inspect_sprite(sprite, false, input.output_path)
  sprite:close()
  return result
end

operations.read_composited_pixels = function(input)
  local sprite = open_sprite(input.source_path)
  local image = render_frame_image(sprite, input.frame + 1)
  local runs, pixel_count = read_image_runs(sprite, image, input)
  local result = {
    frame = input.frame,
    bounds = { x = input.x, y = input.y, width = input.width, height = input.height },
    encoding = "rgba_runs",
    runs = runs,
    pixel_count = pixel_count
  }
  sprite:close()
  return result
end

operations.set_pixel_runs = function(input)
  local sprite = open_sprite(input.source_path)
  local layer = find_layer(sprite, input.layer)
  if layer.isGroup or layer.isTilemap then
    sprite:close()
    fail("INVALID_SELECTOR", "pixel runs require an image layer")
  end
  local frame_number = input.frame + 1
  if frame_number < 1 or frame_number > #sprite.frames then
    sprite:close()
    fail("INVALID_SELECTOR", "frame index is outside the sprite")
  end
  app.transaction("MCP set pixel runs", function()
    local existing = layer:cel(frame_number)
    local image = Image(sprite.spec)
    if existing ~= nil then image:drawImage(existing.image, existing.position) end
    for _, run in ipairs(input.runs or {}) do
      if run.x + run.length > sprite.width or run.y >= sprite.height then
        fail("INVALID_SELECTOR", "pixel run extends outside the sprite")
      end
      local color = parse_color(run.color)
      for x = run.x, run.x + run.length - 1 do image:drawPixel(x, run.y, color) end
    end
    if existing ~= nil then
      existing.image = image
      existing.position = Point(0, 0)
    else
      sprite:newCel(layer, frame_number, image, Point(0, 0))
    end
  end)
  save_copy(sprite, input.output_path)
  local result = inspect_sprite(sprite, false, input.output_path)
  sprite:close()
  return result
end

operations.fill_region = function(input)
  local sprite = open_sprite(input.source_path); local layer=find_layer(sprite,input.layer)
  if layer.isGroup or layer.isTilemap then fail("INVALID_SELECTOR", "fill requires image layer") end
  local frame=input.frame+1; if frame < 1 or frame > #sprite.frames then fail("INVALID_SELECTOR", "frame outside sprite") end
  if input.x >= sprite.width or input.y >= sprite.height then fail("INVALID_SELECTOR", "fill point outside sprite") end
  app.transaction("MCP fill region", function()
    local cel=layer:cel(frame); local image=Image(sprite.spec)
    if cel ~= nil then image:drawImage(cel.image,cel.position) end
    local target=image:getPixel(input.x,input.y); local replacement=parse_color(input.color)
    local queue={{input.x,input.y}}; local head=1; local seen={}
    local visits=0
    while head <= #queue do local point=queue[head]; head=head+1; local x,y=point[1],point[2]; local key=y*sprite.width+x
      if x>=0 and x<sprite.width and y>=0 and y<sprite.height and not seen[key] then seen[key]=true
        visits=visits+1;if visits>input.max_pixel_visits then fail("LIMIT_EXCEEDED","fill exceeds pixel limit") end
        if image:getPixel(x,y)==target then image:drawPixel(x,y,replacement)
          if input.contiguous then table.insert(queue,{x-1,y});table.insert(queue,{x+1,y});table.insert(queue,{x,y-1});table.insert(queue,{x,y+1}) end
        end
      end
    end
    if not input.contiguous then for y=0,sprite.height-1 do for x=0,sprite.width-1 do if image:getPixel(x,y)==target then image:drawPixel(x,y,replacement) end end end end
    if cel then cel.image=image;cel.position=Point(0,0) else sprite:newCel(layer,frame,image,Point(0,0)) end
  end)
  save_copy(sprite,input.output_path);local result=inspect_sprite(sprite,false,input.output_path);sprite:close();return result
end

operations.draw_shapes = function(input)
  local sprite=open_sprite(input.source_path);local layer=find_layer(sprite,input.layer);local frame=input.frame+1
  if layer.isGroup or layer.isTilemap or frame>#sprite.frames then fail("INVALID_SELECTOR","invalid shape target") end
  app.transaction("MCP draw shapes",function() for _,shape in ipairs(input.shapes) do
    if math.min(shape.x1,shape.x2,shape.y1,shape.y2)<0 or math.max(shape.x1,shape.x2)>=sprite.width or math.max(shape.y1,shape.y2)>=sprite.height then fail("INVALID_SELECTOR","shape outside sprite") end
    app.useTool{tool=shape.shape,color=parse_color(shape.color),brush=Brush(1),layer=layer,
      frame=sprite.frames[frame],points={Point(shape.x1,shape.y1),Point(shape.x2,shape.y2)}} end end)
  save_copy(sprite,input.output_path);local result=inspect_sprite(sprite,false,input.output_path);sprite:close();return result
end

operations.edit_selection = function(input)
  local sprite=open_sprite(input.source_path)
  app.transaction("MCP edit selection",function() for _,op in ipairs(input.operations) do
    if op.action=="clear" then sprite.selection:deselect() elseif op.action=="all" then sprite.selection:selectAll() else
      if op.bounds==nil then fail("INVALID_INPUT","selection bounds required") end
      local rect=Rectangle(op.bounds.x,op.bounds.y,op.bounds.width,op.bounds.height)
      if op.action=="replace" then sprite.selection:select(rect) elseif op.action=="add" then sprite.selection:add(rect)
      elseif op.action=="subtract" then sprite.selection:subtract(rect) elseif op.action=="intersect" then sprite.selection:intersect(rect) end
    end end end)
  save_copy(sprite,input.output_path);local result=inspect_sprite(sprite,false,input.output_path);sprite:close();return result
end

operations.apply_outline = function(input)
  local sprite=open_sprite(input.source_path);local layer=find_layer(sprite,input.layer);local frame=input.frame+1
  if layer.isGroup or layer.isTilemap then fail("INVALID_SELECTOR","outline requires a writable image layer") end
  if frame<1 or frame>#sprite.frames then fail("INVALID_SELECTOR","frame index is outside the sprite") end
  app.layer=layer;app.frame=sprite.frames[frame]
  app.transaction("MCP outline",function() app.command.Outline{ui=false,color=parse_color(input.color),place=input.place,matrix=input.matrix} end)
  save_copy(sprite,input.output_path);local result=inspect_sprite(sprite,false,input.output_path);sprite:close();return result
end

operations.draw_strokes = function(input)
  local sprite = open_sprite(input.source_path)
  local layer = find_layer(sprite, input.layer)
  local frame = input.frame + 1
  if layer.isGroup or layer.isTilemap then fail("INVALID_SELECTOR", "strokes require an image layer") end
  if frame < 1 or frame > #sprite.frames then fail("INVALID_SELECTOR", "frame index is outside the sprite") end
  app.transaction("MCP draw strokes", function()
    for _, stroke in ipairs(input.strokes) do
      local points = {}
      for _, point in ipairs(stroke.points) do
        if point.x < 0 or point.x >= sprite.width or point.y < 0 or point.y >= sprite.height then
          fail("INVALID_SELECTOR", "stroke point is outside the sprite")
        end
        table.insert(points, Point(point.x, point.y))
      end
      app.useTool {
        tool = "pencil",
        color = parse_color(stroke.color),
        brush = Brush(stroke.brush_size),
        layer = layer,
        frame = sprite.frames[frame],
        points = points,
        opacity = stroke.opacity,
        freehandAlgorithm = stroke.pixel_perfect and 1 or 0
      }
    end
  end)
  save_copy(sprite, input.output_path)
  local result = inspect_sprite(sprite, false, input.output_path)
  sprite:close()
  return result
end

operations.transform_selection = function(input)
  local sprite = open_sprite(input.source_path)
  local layer = find_layer(sprite, input.layer)
  local frame = input.frame + 1
  local bounds = input.bounds
  if layer.isGroup or layer.isTilemap or layer.isBackground then
    fail("INVALID_SELECTOR", "selection transforms require a non-background image layer")
  end
  if frame < 1 or frame > #sprite.frames then fail("INVALID_SELECTOR", "frame index is outside the sprite") end
  if bounds.x < 0 or bounds.y < 0 or bounds.x + bounds.width > sprite.width or
     bounds.y + bounds.height > sprite.height then
    fail("INVALID_SELECTOR", "selection bounds extend outside the sprite")
  end
  local cel = layer:cel(frame)
  local canvas = Image(sprite.spec)
  canvas:clear()
  if cel ~= nil then canvas:drawImage(cel.image, cel.position) end
  local region = Image(canvas, Rectangle(bounds.x, bounds.y, bounds.width, bounds.height))
  local transformed = region
  if input.action == "flip_horizontal" or input.action == "flip_vertical" or
     input.action == "rotate_90_cw" or input.action == "rotate_90_ccw" then
    transformed = transformed_image(sprite, region, input.action)
  elseif input.action == "scale_nearest" then
    transformed = Image(region)
    transformed:resize(bounds.width * input.scale_x, bounds.height * input.scale_y)
  end
  local target_x = bounds.x + input.offset_x
  local target_y = bounds.y + input.offset_y
  if target_x < 0 or target_y < 0 or target_x + transformed.width > sprite.width or
     target_y + transformed.height > sprite.height then
    fail("INVALID_SELECTOR", "transformed selection extends outside the sprite")
  end
  if bounds.width * bounds.height + transformed.width * transformed.height > input.max_pixel_visits then
    fail("LIMIT_EXCEEDED", "selection transform exceeds pixel visit limit")
  end
  app.transaction("MCP transform selection", function()
    if input.action ~= "copy" then
      canvas:clear(Rectangle(bounds.x, bounds.y, bounds.width, bounds.height))
    end
    canvas:drawImage(transformed, Point(target_x, target_y))
    if cel == nil then cel = sprite:newCel(layer, frame, canvas, Point(0, 0))
    else cel.image = canvas; cel.position = Point(0, 0) end
    sprite.selection:select(Rectangle(target_x, target_y, transformed.width, transformed.height))
  end)
  save_copy(sprite, input.output_path)
  local result = inspect_sprite(sprite, false, input.output_path)
  sprite:close()
  return result
end

local function color_distance(red, green, blue, alpha, target, include_alpha)
  local dr, dg, db = red - target.red, green - target.green, blue - target.blue
  local distance = dr * dr + dg * dg + db * db
  if include_alpha then local da = alpha - target.alpha; distance = distance + da * da end
  return math.sqrt(distance)
end

operations.select_by_color = function(input)
  local sprite = open_sprite(input.source_path)
  local frame = input.frame + 1
  if frame < 1 or frame > #sprite.frames then fail("INVALID_SELECTOR", "selection frame is outside the sprite") end
  local image
  if input.layer == nil then image = render_frame_image(sprite, frame)
  else
    local layer = find_layer(sprite, input.layer)
    if layer.isGroup or layer.isTilemap then fail("INVALID_SELECTOR", "selection requires an image layer") end
    image = Image(sprite.spec); image:clear(); local cel = layer:cel(frame)
    if cel ~= nil then image:drawImage(cel.image, cel.position, cel.opacity) end
  end
  if sprite.width * sprite.height > input.max_pixel_visits then
    fail("LIMIT_EXCEEDED", "color selection exceeds the pixel visit limit")
  end
  local targets = {}
  for _, value in ipairs(input.colors) do table.insert(targets, parse_color(value)) end
  local matches = Selection()
  for y = 0, sprite.height - 1 do
    local run_start = nil
    for x = 0, sprite.width do
      local matched = false
      if x < sprite.width then
        local red, green, blue, alpha = pixel_rgba(sprite, nil, image:getPixel(x, y))
        for _, target in ipairs(targets) do
          if color_distance(red, green, blue, alpha, target, input.include_alpha) <= input.tolerance then
            matched = true; break
          end
        end
      end
      if matched and run_start == nil then run_start = x end
      if not matched and run_start ~= nil then
        matches:add(Rectangle(run_start, y, x - run_start, 1)); run_start = nil
      end
    end
  end
  app.transaction("MCP select by color", function()
    if input.selection_mode == "replace" then sprite.selection = matches
    elseif input.selection_mode == "add" then sprite.selection:add(matches)
    elseif input.selection_mode == "subtract" then sprite.selection:subtract(matches)
    elseif input.selection_mode == "intersect" then sprite.selection:intersect(matches)
    else fail("INVALID_INPUT", "unsupported selection mode") end
  end)
  save_copy(sprite, input.output_path)
  local result = inspect_sprite(sprite, false, input.output_path)
  sprite:close()
  return result
end
