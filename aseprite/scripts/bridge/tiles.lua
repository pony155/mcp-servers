operations.edit_tileset = function(input)
  local sprite = open_sprite(input.source_path)
  app.transaction("MCP edit tileset", function()
    for _, operation in ipairs(input.operations or {}) do
      if operation.action == "add" then
        local tileset = sprite:newTileset(Rectangle(0, 0, operation.tile_width, operation.tile_height))
        tileset.name = operation.name
      else
        local tileset = find_tileset(sprite, operation.tileset)
        if operation.action == "rename" then
          tileset.name = operation.name
        elseif operation.action == "remove_tile" then
          if tileset:tile(operation.tile_index) == nil then fail("INVALID_SELECTOR", "tile was not found") end
          sprite:deleteTile(tileset, operation.tile_index)
        elseif operation.action == "add_tile" or operation.action == "set_tile_pixels" then
          local tile
          if operation.action == "add_tile" then
            tile = operation.tile_index ~= nil and
              sprite:newTile(tileset, operation.tile_index) or sprite:newTile(tileset)
          else
            tile = tileset:tile(operation.tile_index)
            if tile == nil then fail("INVALID_SELECTOR", "tile was not found") end
          end
          local size = tileset.grid.tileSize
          local spec = ImageSpec {
            width = size.width,
            height = size.height,
            colorMode = sprite.colorMode,
            transparentColor = sprite.transparentColor
          }
          local image = operation.action == "set_tile_pixels" and Image(tile.image) or Image(spec)
          for _, pixel in ipairs(operation.pixels or {}) do
            if pixel.x >= size.width or pixel.y >= size.height then
              fail("INVALID_SELECTOR", "tile pixel is outside the tile")
            end
            image:drawPixel(pixel.x, pixel.y, parse_color(pixel.color))
          end
          tile.image = image
        else
          fail("INVALID_INPUT", "unsupported tileset edit action")
        end
      end
    end
  end)
  save_copy(sprite, input.output_path)
  local result = inspect_sprite(sprite, false, input.output_path)
  sprite:close()
  return result
end

operations.inspect_tilesets = function(input)
  local sprite=open_sprite(input.source_path);local tilesets,layers={},{}
  for _,ts in ipairs(sprite.tilesets) do local size=ts.grid.tileSize;table.insert(tilesets,{name=ts.name,tile_width=size.width,tile_height=size.height,tile_count=#ts,base_index=ts.baseIndex}) end
  local function walk(items,prefix) for _,layer in ipairs(items) do local path=prefix=="" and layer.name or prefix.."/"..layer.name;if layer.isTilemap then table.insert(layers,path) end;if layer.isGroup then walk(layer.layers,path) end end end
  walk(sprite.layers,"");sprite:close();return {tilesets=tilesets,tilemap_layers=layers}
end

operations.edit_tilemap = function(input)
  local sprite=open_sprite(input.source_path);local ts=find_tileset(sprite,input.tileset);local layer
  if input.create_layer then app.command.NewLayer{name=input.layer,tilemap=true};layer=app.layer;layer.tileset=ts else layer=find_layer(sprite,input.layer) end
  if not layer.isTilemap then fail("INVALID_SELECTOR","target is not tilemap layer") end
  local frame=input.frame+1;if frame>#sprite.frames then fail("INVALID_SELECTOR","frame outside sprite") end
  app.transaction("MCP edit tilemap",function() local cel=layer:cel(frame);if cel==nil then cel=sprite:newCel(layer,frame) end;local image=Image(cel.image)
    for _,cell in ipairs(input.cells) do if cell.x>=image.width or cell.y>=image.height then fail("INVALID_SELECTOR","tilemap cell outside map") end
      local flags=0;if cell.flip_x then flags=flags+0x20000000 end;if cell.flip_y then flags=flags+0x40000000 end;if cell.flip_diagonal then flags=flags+0x80000000 end
      image:drawPixel(cell.x,cell.y,app.pixelColor.tile(cell.tile_index,flags)) end;cel.image=image end)
  save_copy(sprite,input.output_path);local result=inspect_sprite(sprite,false,input.output_path);sprite:close();return result
end

operations.validate_tileset = function(input)
  local sprite=open_sprite(input.source_path);local ts=find_tileset(sprite,input.tileset);local empty,signatures,duplicates,issues={}, {}, {}, {};local visits=0
  for index=1,#ts-1 do local image=ts:tile(index).image;local signature="";local opaque=0
    for pixel in image:pixels() do visits=visits+1;if visits>input.max_pixel_visits then fail("LIMIT_EXCEEDED","tileset validation exceeds pixel limit") end;local value=pixel();signature=signature..tostring(value)..",";if pixel_alpha(sprite,{isBackground=false},value)>0 then opaque=opaque+1 end end
    if opaque==0 then table.insert(empty,index) end;signatures[signature]=signatures[signature] or {};table.insert(signatures[signature],index)
    if input.check_edges then for y=0,image.height-1 do if image:getPixel(0,y)~=image:getPixel(image.width-1,y) then table.insert(issues,{code="EDGE_X_MISMATCH",severity="warning",message="Opposite horizontal edges differ",tile_indices={index}});break end end end
  end
  for _,group in pairs(signatures) do if #group>1 then table.insert(duplicates,group) end end
  if #empty>0 then table.insert(issues,{code="EMPTY_TILES",severity="warning",message="Tileset contains empty tiles",tile_indices=empty}) end
  for _,group in ipairs(duplicates) do table.insert(issues,{code="DUPLICATE_TILES",severity="warning",message="Tileset contains pixel-identical tiles",tile_indices=group}) end
  sprite:close();return {tileset=input.tileset,valid=true,issues=issues,empty_tiles=empty,duplicate_groups=duplicates}
end

operations.export_tileset = function(input)
  local sprite=open_sprite(input.source_path);local ts=find_tileset(sprite,input.tileset);local size=ts.grid.tileSize;local count=#ts-1;local columns=math.min(input.columns,math.max(count,1));local rows=math.ceil(math.max(count,1)/columns)
  if columns*size.width*rows*size.height>input.max_pixels then fail("LIMIT_EXCEEDED","tileset export exceeds pixel limit") end
  local sheet=Image(columns*size.width,rows*size.height,sprite.colorMode);sheet:clear();local entries={}
  for index=1,count do local x=((index-1)%columns)*size.width;local y=math.floor((index-1)/columns)*size.height;sheet:drawImage(ts:tile(index).image,Point(x,y));table.insert(entries,{index=index,x=x,y=y,width=size.width,height=size.height}) end
  if sprite.colorMode==ColorMode.INDEXED then sheet:saveAs{filename=input.image_output_path,palette=sprite.palettes[1]} else sheet:saveAs(input.image_output_path) end
  write_all(input.data_output_path,json.encode({tileset=input.tileset,tile_width=size.width,tile_height=size.height,tiles=entries}));sprite:close();return {tile_count=count}
end

local function transpose_tile(sprite, source)
  local spec = ImageSpec {width=source.height, height=source.width,
    colorMode=sprite.colorMode, transparentColor=sprite.transparentColor}
  local target = Image(spec); target:clear()
  for y=0,source.height-1 do for x=0,source.width-1 do
    target:drawPixel(y,x,source:getPixel(x,y))
  end end
  return target
end

operations.render_tilemap_preview = function(input)
  local sprite = open_sprite(input.source_path)
  local tileset = find_tileset(sprite, input.tileset)
  local tile_size = tileset.grid.tileSize
  local width, height = input.width_cells * tile_size.width, input.height_cells * tile_size.height
  if width * height > input.max_pixels then fail("LIMIT_EXCEEDED", "tilemap preview exceeds pixel limit") end
  local spec = ImageSpec {width=width,height=height,colorMode=sprite.colorMode,
    transparentColor=sprite.transparentColor}
  local preview = Image(spec); preview:clear()
  for _, cell in ipairs(input.cells) do
    if cell.x >= input.width_cells or cell.y >= input.height_cells or cell.tile_index >= #tileset then
      fail("INVALID_SELECTOR", "tilemap preview cell or tile index is outside bounds")
    end
    if cell.tile_index > 0 then
      local tile = Image(tileset:tile(cell.tile_index).image)
      if cell.flip_diagonal then
        if tile.width ~= tile.height then
          fail("INVALID_INPUT", "diagonal flip requires square tiles")
        end
        tile = transpose_tile(sprite, tile)
      end
      if cell.flip_x then tile:flip(FlipType.HORIZONTAL) end
      if cell.flip_y then tile:flip(FlipType.VERTICAL) end
      preview:drawImage(tile, Point(cell.x*tile_size.width, cell.y*tile_size.height))
    end
  end
  if sprite.colorMode == ColorMode.INDEXED then
    preview:saveAs {filename=input.output_path,palette=sprite.palettes[1]}
  else preview:saveAs(input.output_path) end
  sprite:close()
  return {width=width,height=height}
end

operations.create_tileset_from_sheet = function(input)
  local sprite = open_sprite(input.source_path)
  for _, existing in ipairs(sprite.tilesets) do
    if existing.name == input.name then
      fail("INVALID_INPUT", "tileset name already exists: " .. input.name)
    end
  end
  local layer = find_layer(sprite, input.layer)
  local frame = input.frame + 1
  if layer.isGroup or layer.isTilemap then fail("INVALID_SELECTOR", "sheet must be an image layer") end
  if frame < 1 or frame > #sprite.frames then fail("INVALID_SELECTOR", "sheet frame is outside the sprite") end
  local cel = layer:cel(frame)
  if cel == nil then fail("INVALID_SELECTOR", "sheet cel was not found") end
  local step_x, step_y = input.tile_width + input.spacing, input.tile_height + input.spacing
  local available_width, available_height = sprite.width - input.margin * 2,
    sprite.height - input.margin * 2
  local available_columns = math.floor((available_width + input.spacing) / step_x)
  local available_rows = math.floor((available_height + input.spacing) / step_y)
  local columns = input.columns or available_columns
  if available_columns < 1 or available_rows < 1 or columns < 1 or columns > available_columns then
    fail("INVALID_INPUT", "tile grid does not fit the sprite canvas")
  end
  local count = input.tile_count or columns * available_rows
  if count < 1 or count > columns * available_rows or count > input.max_tiles then
    fail("LIMIT_EXCEEDED", "tile count exceeds the available grid or tool limit")
  end
  if count * input.tile_width * input.tile_height > input.max_pixel_visits then
    fail("LIMIT_EXCEEDED", "tileset extraction exceeds the pixel visit limit")
  end
  local sheet = Image(sprite.spec); sheet:clear(); sheet:drawImage(cel.image, cel.position)
  app.transaction("MCP create tileset from sheet", function()
    local tileset = sprite:newTileset(Rectangle(0, 0, input.tile_width, input.tile_height))
    tileset.name = input.name
    local unique = {}
    for index = 0, count - 1 do
      local column, row = index % columns, math.floor(index / columns)
      local bounds = Rectangle(input.margin + column * step_x,
        input.margin + row * step_y, input.tile_width, input.tile_height)
      local tile_image = Image(sheet, bounds)
      local duplicate = false
      if input.deduplicate then
        for _, existing in ipairs(unique) do
          if tile_image:isEqual(existing) then duplicate = true; break end
        end
      end
      if not duplicate then
        local tile = sprite:newTile(tileset)
        tile.image = tile_image
        table.insert(unique, tile_image)
      end
    end
  end)
  save_copy(sprite, input.output_path)
  local result = inspect_sprite(sprite, false, input.output_path)
  sprite:close()
  return result
end

local function scalar_properties(properties)
  local result = {}
  for key, value in pairs(properties) do
    local kind = type(value)
    if kind == "string" or kind == "number" or kind == "boolean" then
      result[tostring(key)] = value
    end
  end
  return result
end

operations.inspect_tile_metadata = function(input)
  local sprite = open_sprite(input.source_path)
  local tileset = find_tileset(sprite, input.tileset)
  local indices = input.tile_indices or {}
  if #indices == 0 then
    if #tileset > input.max_tiles then fail("LIMIT_EXCEEDED", "tileset exceeds inspection limit") end
    for index = 0, #tileset - 1 do table.insert(indices, index) end
  end
  local tiles = {}
  for _, index in ipairs(indices) do
    local tile = tileset:tile(index)
    if tile == nil then fail("INVALID_SELECTOR", "tile was not found: " .. tostring(index)) end
    table.insert(tiles, {index=index, data=tile.data or "", color=color_info(tile.color).hex,
      properties=scalar_properties(tile.properties)})
  end
  local result = {tileset=input.tileset, base_index=tileset.baseIndex,
    data=tileset.data or "", properties=scalar_properties(tileset.properties), tiles=tiles}
  sprite:close()
  return result
end

operations.edit_tile_metadata = function(input)
  local sprite = open_sprite(input.source_path)
  local tileset = find_tileset(sprite, input.tileset)
  app.transaction("MCP edit tile metadata", function()
    for _, operation in ipairs(input.operations) do
      local target = tileset
      if operation.target == "tile" then
        target = tileset:tile(operation.tile_index)
        if target == nil then fail("INVALID_SELECTOR", "tile was not found") end
      end
      if operation.action == "set" then target.properties[operation.key] = operation.value
      elseif operation.action == "remove" then target.properties[operation.key] = nil
      else fail("INVALID_INPUT", "unsupported tile metadata action") end
    end
  end)
  save_copy(sprite, input.output_path)
  local result = inspect_sprite(sprite, false, input.output_path)
  sprite:close()
  return result
end
