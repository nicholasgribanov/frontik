<?xml version="1.0" encoding="utf-8"?>
<xsl:stylesheet version="1.0" xmlns:xsl="http://www.w3.org/1999/XSL/Transform">

    <xsl:template match="doc">
        <html><body>
            <xsl:apply-templates select="ok" />
            <xsl:apply-templates select="not-ok" />
        </body></html>
    </xsl:template>

    <xsl:template match="ok">
        <xsl:call-template name="result"/>
    </xsl:template>

    <xsl:template name="result">
        <h1>ok</h1>
    </xsl:template>

    <xsl:template match="not-ok">
        <h1>not ok</h1>
    </xsl:template>

</xsl:stylesheet>
