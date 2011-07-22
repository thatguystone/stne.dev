require 'liquid'

module Jekyll
  module Filters

    # Return the url's domain name
    def format_date(date, format=@context.registers[:site].config['date_format'])
      return date.strftime(format)
    end
    
  end
end

