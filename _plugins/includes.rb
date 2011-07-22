module Jekyll
  class AssetTag < Liquid::Tag
    def initialize(tag_name, name, tokens)
      super tag_name, name, tokens
      @type = name.to_s.strip
    end

    def render(context)
      @config = context.registers[:site].config
      
      #only include the assets if they exist
      if !@config.include?(@type)
        return
      end
      
      if Jekyll::ENV == 'production'
        markup "/assets/#{name_with_ext}"
      else
        (assets_for_name.map do |asset|
          markup asset
        end).join("\n")
      end
    end
    
    def name_with_ext
      "all.#{@type}"
    end
    
    def assets_for_name
      if @config.include?(@type)
        @config[@type].map do |asset|
          asset.gsub(/_site\/(css|js)\//, '')
        end
      else
        name_with_ext
      end
    end
  end

  class IncludeJsTag < AssetTag
    def initialize(tag_name, name, tokens)
      super tag_name, 'js', tokens
    end
    
    def markup(src)
      %{<script src="/js/#{src}" type="text/javascript"></script>}.to_s
    end  
  end

  class IncludeCssTag < AssetTag
    def initialize(tag_name, name, tokens)
      super tag_name, 'css', tokens
    end

    def markup(src)
      %{<link href="/css/#{src}" media="screen" rel="stylesheet" type="text/css" />}.to_s
    end
  end

  Liquid::Template.register_tag('include_js', IncludeJsTag)
  Liquid::Template.register_tag('include_css', IncludeCssTag)
end
