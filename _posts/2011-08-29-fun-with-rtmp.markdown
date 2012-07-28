---
layout: post
title: Fun With RTMP

categories: linux

summary: How to capture all RTMP streams on Linux.
---

## Getting

You're going to need the following:

* A modern Linux distro
* `rtmpdump` (can be installed with your distro's package manager)
* An RTMP stream that you have permission to copy and download

## iptables Magic

First, in order to capture RTMP streams, you're going to need to redirect the traffic to something you can intercept (ie.
back to your machine). Since you're using Linux, this is incredibly simple:

{% highlight bash %}
$# iptables -t nat -A OUTPUT -p tcp --dport 1935 \
	 -m owner \! --uid-owner root -j REDIRECT
{% endhighlight %}

To delete the iptables rule:

{% highlight bash %}
$# iptables -t nat -D OUTPUT -p tcp --dport 1935 \
	-m owner \! --uid-owner root -j REDIRECT
{% endhighlight %}

## Hijacking the requests

The following command will create the RTMP interceptor and respawn it once it downloads a stream completely.

{% highlight bash %}
sudo rtmpsuck
{% endhighlight %}

To kill it, issue Ctrl+c, and you're good.

## Note

Notice that these commands are being run as root. You need to run these as root, otherwise you won't be able to intercept
the RTMP calls. Also, in the iptables command, root is mentioned: this tells iptables to only redirect requests to `rtmpsrv`
provided that it wasn't root who made the request.

## Legal

Don't be evil. Respect the laws of your respective country. I am not responsible for how you use this. I only talk
about this topic because I find it interesting, and there's nothing wrong with learning.
