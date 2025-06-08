-- Reaper Lua Script: Export Region to OpenTimelineIO
-- Usage: Set region_name variable and run script

local region_name = "E1" -- Change this to your target region name
local track_index = 0 -- First track (0-indexed)
local fps = 29.97002997002997 -- Default frame rate
-- local fps = 25 -- PAL frame rate
local render_audio = true -- Set to true to also render audio mix of the region

function msg(text)
    reaper.ShowConsoleMsg(tostring(text) .. "\n")
end

function seconds_to_rational_time(seconds)
    return {
        ["OTIO_SCHEMA"] = "RationalTime.1",
        rate = 1.0,
        value = seconds
    }
end

function format_time_range(start_seconds, duration_seconds)
    return {
        ["OTIO_SCHEMA"] = "TimeRange.1",
        start_time = seconds_to_rational_time(start_seconds),
        duration = seconds_to_rational_time(duration_seconds)
    }
end

function get_project_info()
    local project_name = reaper.GetProjectName(0, "")
    if project_name == "" then
        project_name = "Untitled Project"
    end
    local sample_rate = reaper.GetSetProjectInfo(0, "PROJECT_SRATE", 0, false)
    return project_name, sample_rate
end

function find_region_by_name(name)
    local num_markers, num_regions = reaper.CountProjectMarkers(0)
    local total_markers = num_markers + num_regions
    
    for i = 0, total_markers - 1 do
        local retval, isrgn, pos, rgnend, region_name_found, markrgnindexnumber = reaper.EnumProjectMarkers(i)
        if retval and isrgn and region_name_found == name then
            return pos, rgnend, markrgnindexnumber
        end
    end
    return nil, nil, nil
end

function get_media_items_in_region(track, region_start, region_end)
    local items = {}
    local num_items = reaper.CountTrackMediaItems(track)
    
    for i = 0, num_items - 1 do
        local item = reaper.GetTrackMediaItem(track, i)
        local item_start = reaper.GetMediaItemInfo_Value(item, "D_POSITION")
        local item_length = reaper.GetMediaItemInfo_Value(item, "D_LENGTH")
        local item_end = item_start + item_length
        
        -- Check if item overlaps with region
        if item_start < region_end and item_end > region_start then
            local take = reaper.GetActiveTake(item)
            if take then
                -- Get take name (T1, T2, T3, etc.)
                local take_name = reaper.GetTakeName(take)
                if take_name == "" then
                    take_name = "Unnamed Take " .. i
                end
                
                local take_start_offset = reaper.GetMediaItemTakeInfo_Value(take, "D_STARTOFFS")
                local playrate = reaper.GetMediaItemTakeInfo_Value(take, "D_PLAYRATE")
                
                -- Calculate source range in seconds
                local source_in = take_start_offset
                local source_duration = item_length / playrate
                
                -- Calculate timeline range (relative to region start)
                local timeline_in = math.max(0, item_start - region_start)
                local timeline_duration = math.min(region_end - region_start - timeline_in, item_length)
                
                table.insert(items, {
                    name = take_name,
                    source_in = source_in,
                    source_duration = source_duration,
                    timeline_in = timeline_in,
                    timeline_duration = timeline_duration
                })
            end
        end
    end
    
    return items
end

function empty_array()
    -- Return a special marker for empty arrays
    return "JSON_ARRAY"
end

function create_media_reference(name, source_in, source_duration)
    return {
        ["OTIO_SCHEMA"] = "MediaReference.1",
        metadata = {},
        name = name,
        available_range = format_time_range(source_in, source_duration),
        available_image_bounds = json_null()
    }
end

function create_clip(name, source_in, source_duration)
    return {
        ["OTIO_SCHEMA"] = "Clip.2",
        metadata = {},
        name = name,
        source_range = format_time_range(source_in, source_duration),
        effects = empty_array(),
        markers = empty_array(),
        enabled = true,
        media_references = {
            DEFAULT_MEDIA = create_media_reference(name, source_in, source_duration)
        },
        active_media_reference_key = "DEFAULT_MEDIA"
    }
end

function create_track(track_name, clips)
    return {
        ["OTIO_SCHEMA"] = "Track.1",
        metadata = {},
        name = track_name,
        source_range = json_null(),
        effects = empty_array(),
        markers = empty_array(),
        enabled = true,
        children = clips,
        kind = "Video"
    }
end

function create_timeline(project_name, sample_rate, tracks)
    return {
        ["OTIO_SCHEMA"] = "Timeline.1",
        metadata = {},
        name = '"exported from reaper"',
        global_start_time = {
            ["OTIO_SCHEMA"] = "RationalTime.1",
            rate = 96000.0,
            value = 0.0
        },
        tracks = {
            ["OTIO_SCHEMA"] = "Stack.1",
            metadata = {},
            name = "tracks",
            source_range = json_null(),
            effects = empty_array(),
            markers = empty_array(),
            enabled = true,
            children = tracks
        }
    }
end

function json_null()
    -- Return a special marker for null values
    return "JSON_NULL"
end

function is_array(t)
    if type(t) ~= "table" then return false end
    local i = 0
    for _ in pairs(t) do
        i = i + 1
        if t[i] == nil then return false end
    end
    return true
end

function get_ordered_keys(obj, obj_type)
    -- Define field order to match Python OTIO output
    local orders = {
        Timeline = {"OTIO_SCHEMA", "metadata", "name", "global_start_time", "tracks"},
        Stack = {"OTIO_SCHEMA", "metadata", "name", "source_range", "effects", "markers", "enabled", "children"},
        Track = {"OTIO_SCHEMA", "metadata", "name", "source_range", "effects", "markers", "enabled", "children", "kind"},
        Clip = {"OTIO_SCHEMA", "metadata", "name", "source_range", "effects", "markers", "enabled", "media_references", "active_media_reference_key"},
        MediaReference = {"OTIO_SCHEMA", "metadata", "name", "available_range", "available_image_bounds"},
        TimeRange = {"OTIO_SCHEMA", "duration", "start_time"},
        RationalTime = {"OTIO_SCHEMA", "rate", "value"}
    }
    
    local schema = obj["OTIO_SCHEMA"]
    local order = nil
    if schema then
        local schema_type = schema:match("([^%.]+)")
        order = orders[schema_type]
    end
    
    if order then
        local ordered = {}
        -- Add keys in defined order
        for _, key in ipairs(order) do
            if obj[key] ~= nil then
                table.insert(ordered, key)
            end
        end
        -- Add any remaining keys
        for key, _ in pairs(obj) do
            local found = false
            for _, ordered_key in ipairs(ordered) do
                if key == ordered_key then
                    found = true
                    break
                end
            end
            if not found then
                table.insert(ordered, key)
            end
        end
        return ordered
    else
        -- Default: return keys in pairs() order
        local keys = {}
        for k, _ in pairs(obj) do
            table.insert(keys, k)
        end
        return keys
    end
end

function json_encode(obj)
    if obj == "JSON_NULL" then
        return "null"
    elseif obj == "JSON_ARRAY" then
        return "[]"
    elseif type(obj) == "table" then
        if next(obj) == nil then
            return "{}"
        end
        
        if is_array(obj) then
            -- Handle as array
            local parts = {}
            for i = 1, #obj do
                table.insert(parts, json_encode(obj[i]))
            end
            return "[" .. table.concat(parts, ", ") .. "]"
        else
            -- Handle as object with ordered keys
            local parts = {}
            local ordered_keys = get_ordered_keys(obj)
            for _, k in ipairs(ordered_keys) do
                local v = obj[k]
                local key = '"' .. tostring(k) .. '"'
                local value = json_encode(v)
                table.insert(parts, key .. ": " .. value)
            end
            return "{" .. table.concat(parts, ", ") .. "}"
        end
    elseif type(obj) == "string" then
        return '"' .. obj:gsub('"', '\\"') .. '"'
    elseif type(obj) == "boolean" then
        return tostring(obj)
    elseif type(obj) == "number" then
        return tostring(obj)
    else
        return "null"
    end
end

function is_folder_track(track)
    local folder_state = reaper.GetMediaTrackInfo_Value(track, "I_FOLDERDEPTH")
    return folder_state == 1 -- 1 means it's a folder parent
end

function find_track_with_items(region_start, region_end)
    local num_tracks = reaper.CountTracks(0)
    msg("Scanning " .. num_tracks .. " tracks for media items in region...")
    
    for i = 0, num_tracks - 1 do
        local track = reaper.GetTrack(0, i)
        local retval, track_name = reaper.GetSetMediaTrackInfo_String(track, "P_NAME", "", false)
        local is_folder = is_folder_track(track)
        local items = get_media_items_in_region(track, region_start, region_end)
        msg("Track " .. i .. " (" .. track_name .. "): " .. #items .. " items" .. (is_folder and " [FOLDER]" or ""))
        if #items > 0 and not is_folder then
            return track, i, items
        end
    end
    return nil, nil, {}
end

function render_region_audio(region_start, region_end, output_dir, filename)
    msg("Rendering audio for region: " .. region_start .. " to " .. region_end)
    
    -- Configure render settings
    reaper.GetSetProjectInfo(0, "RENDER_SETTINGS", 0, true) -- Master mix (0=master mix)
    reaper.GetSetProjectInfo(0, "RENDER_BOUNDSFLAG", 0, true) -- Custom time bounds
    reaper.GetSetProjectInfo(0, "RENDER_CHANNELS", 2, true) -- Stereo
    reaper.GetSetProjectInfo(0, "RENDER_SRATE", 48000, true) -- 48kHz
    reaper.GetSetProjectInfo(0, "RENDER_STARTPOS", region_start, true) -- Set start position
    reaper.GetSetProjectInfo(0, "RENDER_ENDPOS", region_end, true) -- Set end position
    reaper.GetSetProjectInfo(0, "RENDER_ADDTOPROJ", 0, true) -- Don't add to project, render silent files
    
    -- Set format to WAV 24-bit using correct format
    reaper.GetSetProjectInfo_String(0, "RENDER_FORMAT", "evaw", true)
    
    -- Set output directory (RENDER_FILE is the directory)
    reaper.GetSetProjectInfo_String(0, "RENDER_FILE", output_dir, true)
    
    -- Set filename pattern
    reaper.GetSetProjectInfo_String(0, "RENDER_PATTERN", filename, true)
    
    -- Render using custom bounds
    reaper.Main_OnCommand(42230, 0) -- Render project
    
    msg("Audio rendered to: " .. output_dir .. "/" .. filename)
end

function main()
    local project_name, sample_rate = get_project_info()
    msg("Project: " .. project_name)
    msg("Sample Rate: " .. sample_rate)
    
    -- Find the region
    local region_start, region_end, region_index = find_region_by_name(region_name)
    if not region_start then
        msg("Error: Region '" .. region_name .. "' not found")
        return
    end
    
    local region_duration = region_end - region_start
    msg("Found region '" .. region_name .. "': " .. region_start .. " to " .. region_end .. " (" .. region_duration .. "s)")
    
    -- Find track with media items in the region
    local track, found_track_index, media_items = find_track_with_items(region_start, region_end)
    if not track then
        msg("Error: No tracks found with media items in region")
        return
    end
    
    msg("Using track " .. found_track_index .. " with " .. #media_items .. " media items")
    
    -- Create OTIO clips
    local clips = {}
    for _, item in ipairs(media_items) do
        msg("  " .. item.name .. ": source[" .. item.source_in .. ", " .. (item.source_in + item.source_duration) .. "] timeline[" .. item.timeline_in .. ", " .. (item.timeline_in + item.timeline_duration) .. "]")
        local clip = create_clip(item.name, item.source_in, item.source_duration)
        table.insert(clips, clip)
    end
    
    -- Create track and timeline
    local video_track = create_track("Track 1", clips)
    local timeline = create_timeline(project_name, sample_rate, {video_track})
    
    -- Convert to JSON
    local otio_json = json_encode(timeline)
    
    -- Write to file - save in same directory as the .RPP file
    local project_filename = reaper.GetProjectName(0, "")
    local project_path = reaper.GetProjectPath("")
    -- Get parent directory of project path if it points to Media folder
    if project_path:match("/Media$") then
        project_path = project_path:gsub("/Media$", "")
    end
    local output_file = project_path .. "/" .. region_name .. ".otio"
    
    local file = io.open(output_file, "w")
    if file then
        file:write(otio_json)
        file:close()
        msg("OTIO file written to: " .. output_file)
    else
        msg("Error: Could not write to file " .. output_file)
        return
    end
    
    -- Render audio if enabled
    if render_audio then
        -- Create Mixes directory if it doesn't exist
        local mixes_dir = project_path .. "/Mixes"
        reaper.RecursiveCreateDirectory(mixes_dir, 0)
        
        -- Render audio
        local filename = region_name .. ".wav"
        render_region_audio(region_start, region_end, mixes_dir, filename)
    end
end

-- Run the script
reaper.Undo_BeginBlock()
main()
reaper.Undo_EndBlock("Export Region to OTIO", -1)