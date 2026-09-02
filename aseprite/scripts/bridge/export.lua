operations.render_contact_sheet = function(input)
  local sprite = open_sprite(input.source_path)
  local frame_count = #sprite.frames
  local columns = math.min(input.columns, frame_count)
  local rows = math.ceil(frame_count / columns)
  local cell_width = sprite.width * input.scale + 2
  local cell_height = sprite.height * input.scale + 9
  local sheet_width = columns * cell_width
  local sheet_height = rows * cell_height
  if sheet_width * sheet_height > input.max_pixels then
    sprite:close()
    fail("LIMIT_EXCEEDED", "contact sheet exceeds the pixel limit")
  end
  local sheet = Image(sheet_width, sheet_height, ColorMode.RGB)
  sheet:clear(Rectangle(0, 0, sheet_width, sheet_height), Color { r = 32, g = 35, b = 42 })
  local label_color = app.pixelColor.rgba(230, 230, 230, 255)
  for frame_index = 1, #sprite.frames do
    local zero_index = frame_index - 1
    local column = zero_index % columns
    local row = math.floor(zero_index / columns)
    local origin_x = column * cell_width + 1
    local origin_y = row * cell_height
    draw_number(sheet, zero_index, origin_x, origin_y + 1, label_color)
    local frame_image = Image(sprite.width, sprite.height, ColorMode.RGB)
    frame_image:clear()
    frame_image:drawSprite(sprite, frame_index, Point(0, 0))
    if input.scale ~= 1 then
      frame_image:resize(sprite.width * input.scale, sprite.height * input.scale)
    end
    sheet:drawImage(frame_image, Point(origin_x, origin_y + 7))
  end
  sheet:saveAs(input.output_path)
  sprite:close()
  return { frame_count = frame_count, columns = columns, rows = rows }
end

operations.extract_slices = function(input)
  local sprite = open_sprite(input.source_path)
  local items = {}
  for _, extraction in ipairs(input.extractions) do
    local frame = extraction.frame + 1
    if frame < 1 or frame > #sprite.frames then fail("INVALID_SELECTOR", "slice frame is outside the sprite") end
    local slice = find_slice(sprite, extraction.name)
    if slice == nil then fail("INVALID_SELECTOR", "slice was not found: " .. extraction.name) end
    app.frame = sprite.frames[frame]
    local bounds = slice.bounds
    if bounds.width < 1 or bounds.height < 1 or bounds.x < 0 or bounds.y < 0 or
       bounds.x + bounds.width > sprite.width or bounds.y + bounds.height > sprite.height then
      fail("INVALID_SELECTOR", "slice bounds are empty or outside the sprite")
    end
    local rendered = render_frame_image(sprite, frame)
    local image = Image(rendered, bounds)
    if sprite.colorMode == ColorMode.INDEXED then
      image:saveAs {filename=extraction.output_path, palette=sprite.palettes[1]}
    else
      image:saveAs(extraction.output_path)
    end
    local pivot = nil
    if slice.pivot ~= nil then pivot = {x=slice.pivot.x, y=slice.pivot.y} end
    table.insert(items, {name=extraction.name, frame=extraction.frame,
      bounds=rectangle_info(bounds), pivot=pivot})
  end
  sprite:close()
  return {items=items}
end

operations.export_frames = function(input)
  local sprite = open_sprite(input.source_path)
  local items = {}
  for _, extraction in ipairs(input.exports) do
    local frame = extraction.frame + 1
    if frame < 1 or frame > #sprite.frames then fail("INVALID_SELECTOR", "export frame is outside the sprite") end
    local image = render_frame_image(sprite, frame)
    if sprite.colorMode == ColorMode.INDEXED then
      image:saveAs {filename=extraction.output_path, palette=sprite.palettes[1]}
    else image:saveAs(extraction.output_path) end
    table.insert(items, {frame=extraction.frame})
  end
  sprite:close()
  return {items=items}
end

local function draw_scaled_region(target,source,sx,sy,sw,sh,dx,dy,dw,dh)
  if sw<=0 or sh<=0 or dw<=0 or dh<=0 then return end
  local part=Image(source,Rectangle(sx,sy,sw,sh));if part.width~=dw or part.height~=dh then part:resize(dw,dh) end
  target:drawImage(part,Point(dx,dy))
end

operations.preview_nine_slice = function(input)
  local sprite=open_sprite(input.source_path);local slice=find_slice(sprite,input.slice)
  if slice==nil then fail("INVALID_SELECTOR","slice was not found") end
  local frame=input.frame+1;if frame<1 or frame>#sprite.frames then fail("INVALID_SELECTOR","frame is outside the sprite") end
  app.frame=sprite.frames[frame];local bounds=slice.bounds;local center=slice.center
  if center==nil then fail("INVALID_SELECTOR","slice does not define a nine-slice center") end
  if bounds.width<1 or bounds.height<1 or bounds.x<0 or bounds.y<0 or
    bounds.x+bounds.width>sprite.width or bounds.y+bounds.height>sprite.height then
    fail("INVALID_SELECTOR","slice bounds are empty or outside the sprite")
  end
  local left,top=center.x,center.y;local right=bounds.width-center.x-center.width
  local bottom=bounds.height-center.y-center.height
  if input.width<left+right or input.height<top+bottom then
    fail("INVALID_INPUT","preview target is smaller than fixed nine-slice borders") end
  if input.width*input.height>input.max_pixels then fail("LIMIT_EXCEEDED","nine-slice preview exceeds pixel limit") end
  local rendered=render_frame_image(sprite,frame);local source=Image(rendered,bounds)
  local spec=ImageSpec{width=input.width,height=input.height,colorMode=sprite.colorMode,
    transparentColor=sprite.transparentColor};local target=Image(spec);target:clear()
  local middle_w=input.width-left-right;local middle_h=input.height-top-bottom
  local xs={0,left,left+center.width};local sw={left,center.width,right};local dx={0,left,left+middle_w};local dw={left,middle_w,right}
  local ys={0,top,top+center.height};local sh={top,center.height,bottom};local dy={0,top,top+middle_h};local dh={top,middle_h,bottom}
  for row=1,3 do for col=1,3 do draw_scaled_region(target,source,xs[col],ys[row],sw[col],sh[row],dx[col],dy[row],dw[col],dh[row]) end end
  if sprite.colorMode==ColorMode.INDEXED then target:saveAs{filename=input.output_path,palette=sprite.palettes[1]}
  else target:saveAs(input.output_path) end
  sprite:close();return {width=input.width,height=input.height}
end

operations.export_bitmap_font = function(input)
  local sprite=open_sprite(input.source_path);local max_width,max_height=0,0
  for _,glyph in ipairs(input.glyphs) do
    if glyph.frame>=#sprite.frames or glyph.bounds.x<0 or glyph.bounds.y<0 or
      glyph.bounds.x+glyph.bounds.width>sprite.width or
      glyph.bounds.y+glyph.bounds.height>sprite.height then
      fail("INVALID_SELECTOR","glyph frame or bounds are outside the sprite")
    end
    max_width=math.max(max_width,glyph.bounds.width);max_height=math.max(max_height,glyph.bounds.height)
  end
  local columns=math.min(input.columns,#input.glyphs);local rows=math.ceil(#input.glyphs/columns)
  local cell_width,cell_height=max_width+input.padding*2,max_height+input.padding*2
  local width,height=columns*cell_width,rows*cell_height
  if width*height>input.max_pixels then fail("LIMIT_EXCEEDED","bitmap-font atlas exceeds pixel limit") end
  local atlas=Image(width,height,sprite.colorMode);atlas:clear();local entries={}
  for index,glyph in ipairs(input.glyphs) do
    local frame_image=render_frame_image(sprite,glyph.frame+1)
    local image=Image(frame_image,Rectangle(glyph.bounds.x,glyph.bounds.y,
      glyph.bounds.width,glyph.bounds.height))
    local x=((index-1)%columns)*cell_width+input.padding
    local y=math.floor((index-1)/columns)*cell_height+input.padding
    atlas:drawImage(image,Point(x,y))
    table.insert(entries,{codepoint=glyph.codepoint,frame=glyph.frame,x=x,y=y,
      width=glyph.bounds.width,height=glyph.bounds.height,
      advance=glyph.advance or glyph.bounds.width,bearing_x=glyph.bearing_x,
      bearing_y=glyph.bearing_y})
  end
  if sprite.colorMode==ColorMode.INDEXED then
    atlas:saveAs{filename=input.image_output_path,palette=sprite.palettes[1]}
  else atlas:saveAs(input.image_output_path) end
  write_all(input.data_output_path,json.encode({font=input.font_name,line_height=input.line_height,
    atlas={width=width,height=height,columns=columns,padding=input.padding},glyphs=entries}))
  sprite:close();return {glyph_count=#input.glyphs,line_height=input.line_height}
end
