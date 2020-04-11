var readingtime = new (function ($) {
    "use strict";
    var self = {};
    self.subs = {};
    $(document).ready(function () {
        Reveal.initialize({
            width: '100%',
            height: '100%',

            // Display controls in the bottom right corner
            controls: true,

            // Display a presentation progress bar
            progress: true,

            // Display the page number of the current slide
            slideNumber: true,

            // Push each slide change to the browser history
            history: false,

            // Enable keyboard shortcuts for navigation
            keyboard: true,

            // Enable the slide overview mode
            overview: false,

            // Vertical centering of slides
            center: false,

            // Enables touch navigation on devices with touch input
            touch: true,

            // Loop the presentation
            loop: false,

            // Change the presentation direction to be RTL
            rtl: false,

            // Randomizes the order of slides each time the presentation loads
            shuffle: false,

            // Turns fragments on and off globally
            fragments: true,

            // Flags if the presentation is running in an embedded mode,
            // i.e. contained within a limited portion of the screen
            embedded: false,

            // Flags if we should show a help overlay when the questionmark
            // key is pressed
            help: true,

            // Flags if speaker notes should be visible to all viewers
            showNotes: false,

            // Number of milliseconds between automatically proceeding to the
            // next slide, disabled when set to 0, this value can be overwritten
            // by using a data-autoslide attribute on your slides
            autoSlide: 0,

            // Stop auto-sliding after user input
            autoSlideStoppable: true,

            // Use this method for navigation when auto-sliding
            autoSlideMethod: Reveal.navigateNext,

            // Enable slide navigation via mouse wheel
            mouseWheel: false,

            // Hides the address bar on mobile devices
            hideAddressBar: true,

            // Opens links in an iframe preview overlay
            previewLinks: false,

            // Transition style
            transition: 'slide', // none/fade/slide/convex/concave/zoom

            // Transition speed
            transitionSpeed: 'default', // default/fast/slow

            // Transition style for full page slide backgrounds
            backgroundTransition: 'fade', // none/fade/slide/convex/concave/zoom

            // Number of slides away from the current that are visible
            viewDistance: 3,

            // Parallax background image
            parallaxBackgroundImage: '', // e.g. "'https://s3.amazonaws.com/hakim-static/reveal-js/reveal-parallax-1.jpg'"

            // Parallax background size
            parallaxBackgroundSize: '', // CSS syntax, e.g. "2100px 900px"

            // Number of pixels to move the parallax background per slide
            // - Calculated automatically unless specified
            // - Set to 0 to disable movement along an axis
            parallaxBackgroundHorizontal: null,
            parallaxBackgroundVertical: null

        });
        Reveal.addEventListener('slidechanged', function (event) {
            // event.previousSlide, event.currentSlide, event.indexh, event.indexv
            var index = event.indexh;
            $('.slides .present .reading-word').first().focus();
        });
        $.getJSON(subs_link, function (subs) {
            self.subs = subs
            bookAudio.pageEndTime = bookAudio.getPageEndTime(0);
        })
    });


    self.playAudioAt = function (wordIdx) {
        let wordSub = self.subs.words[wordIdx];
        let currentTime = bookAudio.currentTime();
        var aboutToSayWord = !bookAudio.isPlaying() && currentTime < wordSub['start'] && currentTime > wordSub['start'] - 2;
        if (!aboutToSayWord) {
            bookAudio.play(Math.max(wordSub['start'], 0))
        }
    };

    self.wordFocus = function (pageIdx, wordIdx) {
        Reveal.slide(pageIdx);
        // if it was a user interaction set audio playtime to before this wordIdx
        let pageEndTime = bookAudio.getPageEndTime(wordIdx);
        if (pageEndTime !== 0) {
            bookAudio.pageEndTime = pageEndTime;
            self.playAudioAt(wordIdx);

            $('.reading-word').removeClass('active');
        }

    };

    return self;
})(jQuery);

var bookAudio = new (function () {
    "use strict";
    var self = {};
    self.previousTime = 0;
    self.pageEndTime = 9999999;

    self.isPlaying = function () {
        return !self.audio.paused
    };

    function getSubsAfterBefore(time, end) {
        var subs = [];
        for (var i = 0; i < readingtime.subs.words.length; i++) {
            var sub = readingtime.subs.words[i];
            if (sub.start > time && sub.start < end) {
                subs.push([sub, i]);
            }
        }
        return subs || [[sub, i]]
    }

    self.getPageEndTime = function (subIndex) {
        var $endElement = $('#word-' + subIndex);
        // first element reads the entire text, others just read themselves
        if ($endElement.prev().length !== 0) {
            //actually dont read only read on the first focus
            return 0
            // var sub = readingtime.subs.words[subIndex];
            // return sub.end
        }
        while ($endElement.next().length !== 0) {
            $endElement = $endElement.next();
            subIndex++;
        }
        var sub = readingtime.subs.words[subIndex];

        return sub.end
    };

    self.playlistener = function () {

        //should it be highlighted
        let currentTime = self.currentTime();

        //setfocus on word at index in subs
        //select a range to fix edge case where time can overshoot
        var nextSubsFound = getSubsAfterBefore(self.previousTime, currentTime); //minus some constant to highlight quicker?

        $('.reading-word').removeClass('active');

        for (var i = 0; i < nextSubsFound.length; i++) {
            // var nextSub = nextSubsFound[0];
            var nextSubIndex = nextSubsFound[i][1];
            let $wordElement = $('#word-' + nextSubIndex);
            $wordElement.addClass('active');

        }


        if (self.pageEndTime && currentTime > self.pageEndTime) {
            self.audio.pause();
            self.pageEndTime = null;
        }


        self.previousTime = currentTime;
    };

    self.currentTime = function () {
        return self.audio.currentTime;
    };
    self.play = function (time) {
        self.audio.play();
        self.audio.currentTime = time;
    };

    $(document).ready(function () {
        self.audio = document.getElementById('audioLink'); // todo

        self.audio.addEventListener('timeupdate', self.playlistener);
    })

    return self;
})();