/**
 * @version		2.9.1
 * @package		Frontpage Slideshow
 * @author    JoomlaWorks - http://www.joomlaworks.gr
 * @copyright	Copyright (c) 2006 - 2011 JoomlaWorks, a business unit of Nuevvo Webware Ltd. All rights reserved.
 * @license		Commercial - This code cannot be redistributed without permission from Nuevvo Webware Ltd.
 */

/* --- Slideshow Containers --- */
#fpss-outer-container {/*clear:both;*/width:1200px;border:1px solid #ccc;padding:2px;margin:4px auto;}
#fpss-container {position:relative;width:1200px;}
#fpss-slider {overflow:hidden;background:none;/*clear:both;*/width:1200px;height:900px;}
#slide-loading {background:#000 url(images/loading_black.gif) no-repeat center;text-align:center;width:1200px;height:900px;}
#slide-wrapper {display:none;font-size:11px;text-align:left;width:1200px;height:900px;}
#slide-wrapper #slide-outer {height:900px;}
#slide-wrapper #slide-outer .slide {position:absolute;overflow:hidden;right:0;width:1200px;height:900px;}
#slide-wrapper #slide-outer .slide .slide-inner {margin:0;color:#fff;overflow:hidden;background:#444;height:900px;}
#slide-wrapper #slide-outer .slide .slide-inner a.fpss_img span span span {background:none;}

/* --- Content --- */
.fpss-introtext {font-size:11px;margin:0;padding:0;position:absolute;top:0;bottom:0;left:40px;width:38%;height:100%;background:url(images/transparent_bg.png);}
.fpss-introtext .slidetext {margin:0;padding:12px 8px;}

/* --- Navigation Buttons --- */
#navi-outer {position:relative;margin:0;padding:0;text-align:right;}
#navi-outer ul {position:relative;margin:-28px 8px 0 0;padding:0;/*clear:both;*/float:right;height:16px;}
#navi-outer li {display:none;background:none;padding:0;margin:0;}
#navi-outer li.noimages {display:inline;margin:0;padding:0;}
#navi-outer li.noimages a#fpss-container_next {display:block;width:16px;height:16px;background:url(images/nav-right.png) no-repeat;border:none;float:right;margin:0 4px 0 0;padding:0;}
#navi-outer li.noimages a#fpss-container_playButton {display:none;}
#navi-outer li.noimages a#fpss-container_prev {display:block;width:16px;height:16px;background:url(images/nav-left.png) no-repeat;border:none;float:right;margin:0 4px 0 0;padding:0;}
#navi-outer li.clr {float:none;/*clear:both;*/}

/* --- Notice: Add custom text styling here to overwrite your template's CSS styles! --- */
.fpss-introtext .slidetext h1 {font-family:"Trebuchet MS", Trebuchet, Arial, Verdana, sans-serif;font-size:24px;line-height:24px;margin:0;padding:0;color:#9c0;}
.fpss-introtext .slidetext h1 a {font-family:"Trebuchet MS", Trebuchet, Arial, Verdana, sans-serif;font-size:24px;margin:0;padding:0;color:#9c0;}
.fpss-introtext .slidetext h1 a:hover {font-family:"Trebuchet MS", Trebuchet, Arial, Verdana, sans-serif;font-size:24px;margin:0;padding:0;color:#fff;}
.fpss-introtext .slidetext h2 {display:none;}
.fpss-introtext .slidetext h3 {font-size:11px;margin:2px 0;padding:1px 4px;color:#ccc;border-top:1px solid #aaa;border-bottom:1px solid #aaa;}
.fpss-introtext .slidetext p {margin:4px 0 12px 0;padding:0px;color:#fff;}
.fpss-introtext .slidetext a.readon {margin:0;padding:1px 4px;border:none;background:#222;color:#fff;text-decoration:none;display:inline;}
.fpss-introtext .slidetext a.readon:hover {margin:0;padding:1px 4px;border:none;background:#fff;color:#222;text-decoration:none;display:inline;}

/* --- Generic Styling (highly recommended) --- */
#fpss-outer-container a:active,
#fpss-outer-container a:focus {outline:0;}
#fpss-container img {border:none;}
.fpss-introtext .slidetext img,
.fpss-introtext .slidetext p img {display:none;} /* this will hide images inside the introtext */
.fpss-clr {/*clear:both;*/height:0;line-height:0;}

/* --- End of stylesheet --- */